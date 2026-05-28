import re
import os
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from email_validator import validate_email as val_email, EmailNotValidError
from typing import List, Dict, Any, Optional

from config.database import SessionLocal
from modules.database.models import Lead, Campaign, ScrapingJob
from modules.database.repositories import LeadRepository
from utils.hash_utils import generate_lead_hash
from modules.scraping.serper_bulk_scraper import fetch_serper_results
from modules.analysis.full_audit_runner import run_full_lead_audit

# Logger setup
import logging
logger = logging.getLogger("leadpilot.backend.email_enrichment")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Free email domains list
FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
    "icloud.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
    "live.com",
    "msn.com"
}

# Column aliases for detection
EMAIL_COL_ALIASES = {"email", "email_address", "mail", "e-mail", "contact_email", "email_id", "emailid"}
BUSINESS_NAME_ALIASES = {"business_name", "company", "company_name", "business", "name"}
PERSON_NAME_ALIASES = {"person_name", "owner", "owner_name", "contact_name", "first_name", "last_name", "person"}
PHONE_ALIASES = {"phone", "phone_number", "mobile", "contact_number", "tel", "telephone"}
CITY_ALIASES = {"city", "location", "town"}
COUNTRY_ALIASES = {"country", "state", "region"}
CATEGORY_ALIASES = {"category", "industry", "sector", "business_type"}
WEBSITE_ALIASES = {"website", "domain", "url", "site", "web"}

def parse_uploaded_email_file(file) -> pd.DataFrame:
    """Parses an uploaded CSV or Excel file into a pandas DataFrame."""
    try:
        file_name = file.name if hasattr(file, 'name') else str(file)
        if file_name.lower().endswith('.csv'):
            # If it's a file stream or path
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        return df
    except Exception as e:
        logger.error(f"Failed to parse uploaded file: {e}")
        raise e

def detect_email_column(df: pd.DataFrame) -> str:
    """Detects the email column name automatically from DataFrame."""
    cols = list(df.columns)
    # 1. Look for exact matches or normalized alias matches
    for col in cols:
        norm = str(col).lower().strip().replace(" ", "_").replace("-", "_")
        if norm in EMAIL_COL_ALIASES or "email" in norm:
            return col
    # 2. Fallback: return the first column if only one column exists
    if df.shape[1] == 1:
        return cols[0]
    
    # 3. Last resort fallback
    for col in cols:
        first_val = str(df[col].iloc[0]).strip() if len(df) > 0 else ""
        if "@" in first_val:
            return col
            
    raise ValueError("Could not detect email column in the uploaded file.")

def validate_email(email: str) -> Optional[str]:
    """Validates and normalizes an email address using email_validator."""
    if not email or not isinstance(email, str):
        return None
    try:
        # validate and get info
        valid = val_email(email.strip())
        return valid.email
    except EmailNotValidError:
        return None

def extract_domain(email: str) -> str:
    """Extracts domain from a validated email address."""
    if not email or "@" not in email:
        return ""
    return email.split("@")[-1].lower().strip()

def is_free_email_domain(domain: str) -> bool:
    """Identifies if a domain is a free email provider."""
    return domain.lower().strip() in FREE_EMAIL_DOMAINS

def guess_website_from_domain(domain: str) -> List[str]:
    """Generates candidate website URLs from a domain, trying https first."""
    domain_clean = domain.strip().lower()
    return [
        f"https://{domain_clean}",
        f"https://www.{domain_clean}",
        f"http://{domain_clean}",
        f"http://www.{domain_clean}"
    ]

def fetch_website(url: str) -> tuple:
    """Attempts to GET the website URL and returns (html_text, final_url)."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    }
    try:
        # verify=True is standard and safe
        r = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        if r.status_code == 200:
            return r.text, r.url
    except Exception as e:
        logger.debug(f"Failed to fetch website {url}: {e}")
    return None, None

def extract_business_name(html: str, domain: str) -> str:
    """Extracts business name from HTML metadata or title tags."""
    if not html:
        return domain.split(".")[0].capitalize()
    
    try:
        soup = BeautifulSoup(html, "html.parser")
        
        # 1. og:site_name
        meta_site = soup.find("meta", property="og:site_name")
        if meta_site and meta_site.get("content"):
            return meta_site.get("content").strip()
            
        # 2. og:title
        meta_title = soup.find("meta", property="og:title")
        if meta_title and meta_title.get("content"):
            return meta_title.get("content").strip()
            
        # 3. Page title tag
        if soup.title and soup.title.string:
            title_text = soup.title.string.strip()
            # Clean common title formats like "Business Name - Home" or "Home | Business Name"
            for separator in ["-", "|", "—", ":"]:
                if separator in title_text:
                    parts = title_text.split(separator)
                    # Guess the one that is NOT "Home" or "Welcome"
                    for p in parts:
                        p_clean = p.strip()
                        if p_clean.lower() not in ["home", "homepage", "welcome", "index"]:
                            return p_clean
            return title_text
            
        # 4. Fallback to h1
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            return h1.get_text(strip=True)
            
    except Exception as e:
        logger.warning(f"Error parsing business name: {e}")
        
    return domain.split(".")[0].capitalize()

def extract_person_name(html: str) -> Optional[str]:
    """Attempts to parse potential contact/person name from HTML content."""
    if not html:
        return None
    try:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text()
        
        # Simple heuristic name searches: "Hi, I'm [Name]" or "Founded by [Name]" or "Contact [Name]"
        patterns = [
            r"(?:founded\s+by|owner|founder|ceo|president)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})",
            r"(?:hi|hello),\s+I'm\s+([A-Z][a-z]+\s+[A-Z][a-z]+)",
            r"([A-Z][a-z]+\s+[A-Z][a-z]+),\s+(?:Founder|CEO|Director|Owner)"
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1).strip()
                # Ensure it doesn't match standard navigation keywords
                if not any(kw in name.lower() for kw in ["about", "contact", "home", "service", "privacy", "terms"]):
                    return name
    except Exception:
        pass
    return None

def extract_phone(html: str) -> Optional[str]:
    """Extracts a phone number using standard international regex patterns from HTML."""
    if not html:
        return None
    try:
        # Standard phone number regex
        phone_pattern = r"(?<!\d)(?:\+?\d{1,3}[\s.-]*)?\(?\d{2,5}\)?[\s.-]*\d{3,5}[\s.-]*\d{3,6}(?!\d)"
        phones = re.findall(phone_pattern, html)
        for phone in phones:
            cleaned = re.sub(r"\D", "", phone)
            if 8 <= len(cleaned) <= 15 and len(set(cleaned)) > 2:
                # Format candidate nicely
                return phone.strip()
    except Exception:
        pass
    return None

def extract_social_links(html: str) -> Dict[str, str]:
    """Extracts social media platform URLs from HTML links."""
    socials = {}
    if not html:
        return socials
    try:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            href_lower = href.lower()
            if "facebook.com" in href_lower and "facebook" not in socials:
                socials["facebook"] = href
            elif "instagram.com" in href_lower and "instagram" not in socials:
                socials["instagram"] = href
            elif "linkedin.com" in href_lower and "linkedin" not in socials:
                socials["linkedin"] = href
            elif "twitter.com" in href_lower or "x.com" in href_lower:
                if "twitter" not in socials:
                    socials["twitter"] = href
            elif "youtube.com" in href_lower and "youtube" not in socials:
                socials["youtube"] = href
    except Exception:
        pass
    return socials

def infer_category(html_text: str) -> str:
    """Guesses the business category based on keyword matches in HTML content."""
    if not html_text:
        return "General Business"
        
    text = html_text.lower()
    
    # Categorization mapping
    categories = {
        "Salon & Beauty": ["salon", "haircut", "spa", "nails", "makeup", "beauty", "massage", "barber"],
        "Medical & Dental": ["dental", "dentist", "clinic", "doctor", "medical", "hospital", "patient", "pediatric"],
        "Restaurant & Food": ["restaurant", "cafe", "menu", "order", "delivery", "food", "dining", "chef", "bakery"],
        "Education & Schools": ["school", "college", "university", "admission", "course", "training", "education", "student"],
        "Real Estate": ["real estate", "property", "apartment", "villa", "rent", "buy", "realtor", "broker", "home sale"],
        "Fitness & Gym": ["gym", "fitness", "workout", "trainer", "yoga", "crossfit", "coaching", "membership"],
        "Legal & Financial": ["lawyer", "attorney", "financial", "accounting", "tax", "consulting", "advisor", "audit"]
    }
    
    best_category = "General Business"
    max_matches = 0
    
    for cat, keywords in categories.items():
        matches = sum(text.count(kw) for kw in keywords)
        if matches > max_matches:
            max_matches = matches
            best_category = cat
            
    return best_category

def enrich_email_lead(row: dict, campaign_id: str = None, db = None) -> dict:
    """
    Enriches a single email lead using web scraping, local audit pipelines,
    and optional Serper.dev lookups.
    """
    # Create DB session if not supplied
    local_session = False
    if db is None:
        db = SessionLocal()
        local_session = True
        
    lead_repo = LeadRepository(db)
    
    email_raw = row.get("email")
    email = validate_email(email_raw)
    
    # Summary of default enriched lead data
    enriched_data = {
        "email": email_raw,
        "business_name": row.get("business_name") or "Unknown Business",
        "person_name": row.get("person_name"),
        "phone": row.get("phone"),
        "city": row.get("city") or row.get("location") or "Unknown",
        "country": row.get("country"),
        "category": row.get("category"),
        "website": row.get("website"),
        "domain": None,
        "enrichment_status": "NEEDS_MANUAL_REVIEW",
        "digital_presence_status": "Not verified",
        "recommended_service": "General Development",
        "pitch_angle": "Standard partnership pitch",
        "pain_points": [],
        "ai_report": None
    }
    
    try:
        # 1. Invalid email check
        if not email:
            enriched_data["enrichment_status"] = "INVALID_EMAIL"
            return enriched_data
            
        enriched_data["email"] = email
        domain = extract_domain(email)
        enriched_data["domain"] = domain
        
        # 2. Check if Domain is generic or private
        if is_free_email_domain(domain):
            business_name = row.get("business_name")
            if not business_name:
                # No business name provided
                enriched_data["enrichment_status"] = "FREE_EMAIL_NO_BUSINESS_NAME"
                return enriched_data
                
            # If business name is provided, lookup using Serper.dev
            logger.info(f"Looking up free email lead '{business_name}' via Serper...")
            serp_query = f"{business_name} {enriched_data['city']} {enriched_data['country'] or ''}".strip()
            serp_results = fetch_serper_results(serp_query)
            
            if serp_results:
                first_res = serp_results[0]
                enriched_data["website"] = first_res.get("link")
                enriched_data["business_name"] = first_res.get("title") or business_name
                enriched_data["enrichment_status"] = "PARTIALLY_ENRICHED"
                
                # Now try to enrich from the discovered website!
                site_url = enriched_data["website"]
                if site_url:
                    html, final_url = fetch_website(site_url)
                    if html:
                        enriched_data["website"] = final_url
                        if not row.get("phone"):
                            enriched_data["phone"] = extract_phone(html)
                        enriched_data["category"] = infer_category(html)
                        
            else:
                # Serper query failed to return results
                enriched_data["enrichment_status"] = "NEEDS_MANUAL_REVIEW"
                
        else:
            # Business email domain
            guessed_urls = guess_website_from_domain(domain)
            site_found = False
            html, final_url = None, None
            
            for url in guessed_urls:
                html, final_url = fetch_website(url)
                if html:
                    site_found = True
                    break
                    
            if not site_found:
                # Website not reachable
                enriched_data["website"] = f"https://{domain}"
                enriched_data["enrichment_status"] = "WEBSITE_NOT_FOUND"
                return enriched_data
                
            # Website found, scrape details
            enriched_data["website"] = final_url
            enriched_data["business_name"] = extract_business_name(html, domain)
            enriched_data["category"] = infer_category(html)
            
            # Extract names & numbers if they weren't in CSV
            if not row.get("person_name"):
                enriched_data["person_name"] = extract_person_name(html)
            if not row.get("phone"):
                enriched_data["phone"] = extract_phone(html)
                
            socials = extract_social_links(html)
            
            # 3. Create mock temporary lead to execute standard audit runner
            # We want to perform the standard audit & AI pitch generation
            from modules.database.models import get_or_create_default_user
            user = get_or_create_default_user(db)
            temp_lead = Lead(
                user_id=user.id,
                business_name=enriched_data["business_name"],
                category=enriched_data["category"],
                phone=enriched_data["phone"],
                email=email,
                website=enriched_data["website"]
            )
            
            logger.info(f"Running full LeadPilot audit pipeline for: {enriched_data['business_name']}")
            audit_results = run_full_lead_audit(temp_lead)
            
            # Extract AI Pitch Engine Pitch & Recommendation
            ai_report = audit_results.get("ai_report", {})
            enriched_data["ai_report"] = ai_report
            enriched_data["pain_points"] = audit_results.get("pain_points", [])
            
            if ai_report and "error" not in ai_report:
                enriched_data["digital_presence_status"] = ai_report.get("opportunity_level", "Medium Opportunity")
                enriched_data["recommended_service"] = ai_report.get("recommended_services", [{"service_name": "Website Development"}])[0].get("service_name")
                enriched_data["pitch_angle"] = ai_report.get("main_pitch_angle", "Digital Optimization Pitch")
                enriched_data["enrichment_status"] = "ENRICHED"
            else:
                # Audit succeeded but AI report failed
                enriched_data["enrichment_status"] = "PARTIALLY_ENRICHED"
                
    except Exception as e:
        logger.error(f"Enrichment error on row {email_raw}: {e}")
        enriched_data["enrichment_status"] = "NEEDS_MANUAL_REVIEW"
    finally:
        if local_session:
            db.close()
            
    return enriched_data

def save_enriched_lead(enriched_data: dict, campaign_id: str, scraping_job_id: str, db) -> tuple:
    """
    Saves an enriched lead cleanly to Supabase PostgreSQL, taking care of deduplication
    by email, domain, and business name.
    """
    email = enriched_data.get("email")
    domain = enriched_data.get("domain")
    business_name = enriched_data.get("business_name")
    
    # 1. Deduplication check
    repo = LeadRepository(db)
    
    # Generate standard Lead Hash
    lead_hash = generate_lead_hash(
        business_name=business_name,
        email=email,
        website=enriched_data.get("website"),
        location=enriched_data.get("city")
    )
    
    # Check by email first, then lead hash
    existing = None
    if email:
        existing = db.query(Lead).filter(Lead.email == email).first()
    if not existing:
        existing = repo.get_by_lead_hash(lead_hash)
        
    if existing:
        # Deduplication match: update empty/missing fields on existing lead safely
        update_fields = {}
        if not existing.website and enriched_data.get("website"):
            update_fields["website"] = enriched_data.get("website")
        if (not existing.business_name or existing.business_name == "Unknown Business") and business_name:
            update_fields["business_name"] = business_name
        if not existing.phone and enriched_data.get("phone"):
            update_fields["phone"] = enriched_data.get("phone")
        if not existing.category and enriched_data.get("category"):
            update_fields["category"] = enriched_data.get("category")
        if not existing.domain and domain:
            update_fields["domain"] = domain
            
        # Update enrichment metadata
        update_fields["enrichment_status"] = enriched_data.get("enrichment_status")
        update_fields["enrichment_source"] = "email_only_enrichment"
        update_fields["enriched_at"] = datetime.utcnow()
        
        repo.update(existing.id, **update_fields)
        return existing, "updated"
        
    # 2. Create new Lead record
    from modules.database.models import get_or_create_default_user
    user = get_or_create_default_user(db)
    lead_obj = Lead(
        user_id=user.id,
        campaign_id=campaign_id,
        scraping_job_id=scraping_job_id,
        business_name=business_name,
        category=enriched_data.get("category") or "General Business",
        phone=enriched_data.get("phone"),
        email=email,
        website=enriched_data.get("website"),
        domain=domain,
        city=enriched_data.get("city"),
        country=enriched_data.get("country"),
        source="email_only_enrichment",
        has_email=bool(email),
        has_phone=bool(enriched_data.get("phone")),
        has_website=bool(enriched_data.get("website")),
        lead_hash=lead_hash,
        status="NEW_LEAD",
        enrichment_status=enriched_data.get("enrichment_status"),
        enrichment_source="email_only_enrichment",
        enriched_at=datetime.utcnow() if enriched_data.get("enrichment_status") in ["ENRICHED", "PARTIALLY_ENRICHED"] else None,
        raw_data={
            "digital_presence_status": enriched_data.get("digital_presence_status"),
            "recommended_service": enriched_data.get("recommended_service"),
            "pitch_angle": enriched_data.get("pitch_angle"),
            "ai_report": enriched_data.get("ai_report")
        }
    )
    
    db.add(lead_obj)
    db.commit()
    db.refresh(lead_obj)
    
    # Save child records (AI Reports, PainPoints, Recommendations) if ENRICHED
    ai_report = enriched_data.get("ai_report")
    if ai_report and "error" not in ai_report:
        try:
            from modules.database.models import AnalysisReport, PainPoint, RecommendedService, OutreachMessage, AnalysisJob
            
            # Create completed AnalysisJob
            job = AnalysisJob(
                lead_id=lead_obj.id,
                website_url=lead_obj.website,
                status="COMPLETED",
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            db.add(job)
            db.flush()
            
            # Create AnalysisReport
            report = AnalysisReport(
                lead_id=lead_obj.id,
                job_id=job.id,
                website_url=lead_obj.website,
                has_website=True,
                overall_score=ai_report.get("technical_summary", {}).get("digital_health_score", 80),
                opportunity_level=ai_report.get("opportunity_level", "Medium"),
                raw_audit_json=ai_report,
                pain_points_json=ai_report.get("top_pain_points", []),
                recommended_services_json=ai_report.get("recommended_services", []),
                ai_report_json=ai_report
            )
            db.add(report)
            db.flush()
            
            # Save rule pain points
            for pp in enriched_data.get("pain_points", []):
                p_obj = PainPoint(
                    lead_id=lead_obj.id,
                    job_id=job.id,
                    type=pp.get("type", "General"),
                    severity=pp.get("severity", "medium"),
                    title=pp.get("title", "Optimization"),
                    description=pp.get("description"),
                    evidence=pp.get("evidence"),
                    recommended_service=pp.get("recommended_service")
                )
                db.add(p_obj)
                
            # Save rule recommended services
            for svc in ai_report.get("recommended_services", []):
                s_obj = RecommendedService(
                    lead_id=lead_obj.id,
                    job_id=job.id,
                    service_name=svc.get("service_name"),
                    priority=svc.get("priority", "Medium"),
                    reason=svc.get("reason"),
                    pitch_angle=svc.get("pitch_angle")
                )
                db.add(s_obj)
                
            # Save AI generated Outreach Message
            outreach = ai_report.get("outreach", {})
            if outreach:
                msg_obj = OutreachMessage(
                    lead_id=lead_obj.id,
                    report_id=report.id,
                    email_type="Enrichment Outreach",
                    tone="Professional",
                    length="Concise",
                    service_focus=svc.get("service_name") if ai_report.get("recommended_services") else "General Development",
                    subject_lines=[outreach.get("email_subject", "Boost Discoverability")],
                    email_body=outreach.get("email_body"),
                    whatsapp_message=outreach.get("whatsapp_message"),
                    linkedin_message=outreach.get("linkedin_message")
                )
                db.add(msg_obj)
                
            db.commit()
        except Exception as ex:
            db.rollback()
            logger.error(f"Failed to save sub-records for lead {lead_obj.id}: {ex}")
            
    return lead_obj, "created"
