import time
import logging
import json
import re
import phonenumbers
from phonenumbers import NumberParseException
from typing import List, Dict, Any, Callable
from sqlalchemy.orm import Session

from modules.scraping.query_expander import generate_query_variations
from modules.scraping.serper_bulk_scraper import fetch_serper_results
from modules.scraping.lead_cleaner import dedupe_serp_results, get_domain
from modules.scraping.website_contact_scraper import scrape_contact_info
from modules.database.repositories import LeadRepository, JobRepository
from modules.database.models import Lead, ScrapingJob, RawScrapedRecord
from config.database import SessionLocal
from utils.constants import JOB_STOPPED
from utils.hash_utils import generate_lead_hash as build_lead_hash
from utils.type_utils import safe_float, safe_int

logger = logging.getLogger(__name__)


def generate_business_hash(title: str, domain: str, query: str) -> str:
    """
    Generates a business-level hash.

    This helps avoid duplicates where the same business appears with
    different URLs/pages from the same domain.
    """
    return build_lead_hash(
        business_name=title,
        website=f"https://{domain}" if domain else None,
        location=query,
        domain=domain,
    )


def infer_phone_region(location: str = "", query: str = "") -> str | None:
    """
    Infer phone region from location/query.

    Important:
    - This is only for local numbers without country code.
    - Numbers with +country_code are parsed globally.
    - If region is unknown, we do NOT force IN/India.
    """

    text = f"{location} {query}".lower()

    region_keywords = {
        "IN": [
            "india", "delhi", "new delhi", "mumbai", "bangalore", "bengaluru",
            "hyderabad", "chennai", "pune", "kolkata", "noida", "greater noida",
            "gurgaon", "gurugram", "ahmedabad", "jaipur", "lucknow", "surat",
            "indore", "bhopal", "patna", "kanpur", "ghaziabad", "faridabad"
        ],
        "GB": [
            "uk", "united kingdom", "england", "britain", "great britain",
            "london", "manchester", "birmingham", "liverpool", "leeds",
            "glasgow", "edinburgh", "bristol", "sheffield"
        ],
        "US": [
            "usa", "us", "united states", "america", "new york", "los angeles",
            "california", "chicago", "houston", "texas", "florida", "miami",
            "san francisco", "washington", "boston", "seattle"
        ],
        "AE": [
            "uae", "united arab emirates", "dubai", "abu dhabi", "sharjah",
            "ajman"
        ],
        "CA": [
            "canada", "toronto", "vancouver", "montreal", "ottawa", "calgary"
        ],
        "AU": [
            "australia", "sydney", "melbourne", "brisbane", "perth", "adelaide"
        ],
        "SG": [
            "singapore"
        ],
        "DE": [
            "germany", "berlin", "munich", "hamburg", "frankfurt"
        ],
        "FR": [
            "france", "paris", "lyon", "marseille"
        ],
        "NL": [
            "netherlands", "amsterdam", "rotterdam"
        ],
        "IT": [
            "italy", "rome", "milan"
        ],
        "ES": [
            "spain", "madrid", "barcelona"
        ],
        "SA": [
            "saudi arabia", "riyadh", "jeddah"
        ],
        "QA": [
            "qatar", "doha"
        ],
        "KW": [
            "kuwait"
        ],
        "OM": [
            "oman", "muscat"
        ],
        "BH": [
            "bahrain", "manama"
        ],
        "MY": [
            "malaysia", "kuala lumpur"
        ],
        "NZ": [
            "new zealand", "auckland", "wellington"
        ],
        "ZA": [
            "south africa", "cape town", "johannesburg"
        ],
    }

    for region, keywords in region_keywords.items():
        if any(keyword in text for keyword in keywords):
            return region

    return None


def looks_like_fake_number(phone: str) -> bool:
    """
    Reject obvious fake phone-like values:
    decimals, ratings, coordinates, prices, dates, weird fragments.
    """

    if not phone:
        return True

    phone = str(phone).strip()

    # Decimal / coordinate / rating-like values
    if "." in phone:
        return True

    digits = re.sub(r"\D", "", phone)

    if not (8 <= len(digits) <= 15):
        return True

    # Dummy numbers like 0000000000, 1111111111
    if len(set(digits)) <= 2:
        return True

    # Too many fragments like 46-4-93-12-04
    if phone.count("-") > 3:
        return True

    # Too many spaces/fragments can be noisy
    if len(re.findall(r"\d+", phone)) > 5:
        return True

    # Year/date-like fragments
    if re.search(r"\b(19|20)\d{2}\b", phone) and len(digits) < 10:
        return True

    return False


def format_raw_phone(phone: str) -> str | None:
    """
    Return a clean raw phone without forcing wrong country code.
    Used when region is unknown and phone has no +country code.
    """

    if looks_like_fake_number(phone):
        return None

    phone = str(phone).strip()

    # Normalize spaces
    phone = re.sub(r"\s+", " ", phone)

    return phone


def normalize_phone_number(phone: str, default_region: str | None = None) -> str | None:
    """
    Validate and normalize phone number.

    Rules:
    1. If number starts with + or 00, parse globally.
    2. If number has no country code and default_region is known, parse using that region.
    3. If number has no country code and default_region is unknown, keep raw clean number.
       This avoids wrongly adding +91 to London/foreign numbers.
    """

    if not phone:
        return None

    phone = str(phone).strip()

    if looks_like_fake_number(phone):
        return None

    try:
        if phone.startswith("+"):
            parsed = phonenumbers.parse(phone, None)

        elif phone.startswith("00"):
            parsed = phonenumbers.parse("+" + phone[2:], None)

        else:
            # Important fix:
            # Do not force India when region is unknown.
            if not default_region:
                return format_raw_phone(phone)

            parsed = phonenumbers.parse(phone, default_region)

        if not phonenumbers.is_possible_number(parsed):
            return None

        if not phonenumbers.is_valid_number(parsed):
            # If region-based validation fails for a local number,
            # keep raw clean number instead of forcing wrong country code.
            if not phone.startswith("+") and not phone.startswith("00"):
                return format_raw_phone(phone)
            return None

        return phonenumbers.format_number(
            parsed,
            phonenumbers.PhoneNumberFormat.INTERNATIONAL
        )

    except NumberParseException:
        # If parsing fails but the number looks clean, keep it raw.
        # This avoids losing valid local numbers from unknown countries.
        if not phone.startswith("+") and not phone.startswith("00"):
            return format_raw_phone(phone)
        return None


def extract_contact_from_snippet(snippet: str, default_region: str | None = None) -> dict:
    """
    Extract emails and valid phone numbers from SERP snippet.

    SERP snippets are noisy, so phone extraction is strict:
    - decimal values removed
    - candidates validated
    - wrong +91 forcing avoided
    """

    if not snippet:
        return {
            "emails": [],
            "phones": []
        }

    # -------------------------------
    # 1. Extract Emails
    # -------------------------------
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    snippet_emails = re.findall(email_pattern, snippet)

    clean_emails = [
        e.lower().strip()
        for e in snippet_emails
        if not e.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"))
    ]

    # -------------------------------
    # 2. Clean text before phone search
    # -------------------------------
    # Remove decimals like 8.76, 52.84, 14.2064, 46-4.93-12.04
    phone_search_text = re.sub(r"\d+\.\d+", " ", snippet)

    # -------------------------------
    # 3. Extract phone-like candidates
    # -------------------------------
    candidate_phone_pattern = r"""
    (?<![\w.])
    (?:
        (?:\+|00)?\d{1,4}[\s().-]*
    )?
    (?:
        \(?\d{2,5}\)?[\s().-]*
    )?
    \d{3,5}[\s().-]+\d{3,5}
    (?:[\s().-]+\d{2,5})?
    (?![\w.])
    |
    (?<![\w.])
    (?:\+|00)?\d{8,15}
    (?![\w.])
    """

    candidates = re.findall(candidate_phone_pattern, phone_search_text, re.VERBOSE)

    valid_phones = set()

    for candidate in candidates:
        formatted_phone = normalize_phone_number(
            candidate,
            default_region=default_region
        )

        if formatted_phone:
            valid_phones.add(formatted_phone)

    return {
        "emails": list(set(clean_emails)),
        "phones": list(valid_phones)
    }


def clean_phone_list(phones: list[str], default_region: str | None = None) -> list[str]:
    """
    Clean and validate phone list from snippet + website scraper.

    Important:
    - Does not force +91.
    - Uses default_region only when location/query clearly indicates country.
    - Keeps clean raw local numbers if country is unknown.
    """

    valid_phones = set()

    for phone in phones or []:
        formatted_phone = normalize_phone_number(
            str(phone),
            default_region=default_region
        )

        if formatted_phone:
            valid_phones.add(formatted_phone)

    return list(valid_phones)


def build_contact_key(email: str | None, phone: str | None) -> str | None:
    """
    Build a contact-level duplicate key.

    This prevents saving the same business multiple times when it appears
    with different URLs but same email/phone.
    """

    parts = []

    if email:
        clean_email = email.lower().strip()
        if clean_email:
            parts.append(f"email:{clean_email}")

    if phone:
        phone_digits = re.sub(r"\D", "", str(phone))
        if phone_digits:
            parts.append(f"phone:{phone_digits}")

    if not parts:
        return None

    return "|".join(parts)


def _save_raw_record(db: Session, job_id: str, campaign_id: str, title: str, link: str, email: str, phone: str, location: str, main_query: str, page: str, res: dict, status: str, skip_reason: str):
    try:
        raw_record = RawScrapedRecord(
            job_id=job_id,
            campaign_id=campaign_id,
            platform="serper_bulk",
            business_name=title,
            website=link,
            result_url=link,
            email=email,
            phone=phone,
            address=location,
            category=main_query,
            page=str(page),
            source="serper_bulk",
            raw_data=res,
            status=status,
            skip_reason=skip_reason
        )
        db.add(raw_record)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save raw record: {e}")


def run_bulk_serper_scraping(
    db: Session,
    campaign_id: str,
    job_id: str,
    main_query: str,
    location: str = "",
    target_count: int = 5000,
    max_query_variations: int = 30,
    max_pages_per_query: int = 10,
    scrape_websites: bool = True,
    progress_callback: Callable = None
) -> dict:
    """
    Orchestrates bulk SERP scraping using Serper.dev and website extraction.
    Saves leads in real-time as they are found.
    """

    summary = {
        "status": "started",
        "queries_processed": 0,
        "pages_processed": 0,
        "raw_results_found": 0,
        "unique_leads_saved": 0,
        "emails_found": 0,
        "phones_found": 0,
        "total_duplicates": 0,
        "errors": []
    }

    def is_stopped():
        thread_db = SessionLocal()
        try:
            job = thread_db.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
            return job and job.status == JOB_STOPPED
        finally:
            thread_db.close()

    try:
        # 1. Expand Queries
        queries = generate_query_variations(
            main_query,
            location,
            limit=max_query_variations
        )

        logger.info(f"Generated {len(queries)} query variations for: {main_query}")

        lead_repo = LeadRepository(db)
        job_repo = JobRepository(db)

        # Duplicate protection for this running job
        seen_urls = set()
        seen_business_domains = set()
        seen_contact_keys = set()

        # 2. Loop through queries
        for q_idx, query in enumerate(queries):
            if is_stopped():
                logger.info("Stopping bulk scraping as per user request.")
                break

            if summary["unique_leads_saved"] >= target_count:
                logger.info(f"Target count reached: {target_count}")
                break

            # Dynamic phone region for this query
            # Example:
            # location="London" => GB
            # location="Dubai" => AE
            # location="Delhi" => IN
            # unknown => None, no forced +91
            phone_region = infer_phone_region(location=location, query=query)

            if progress_callback:
                progress_callback(
                    f"Processing query {q_idx + 1}/{len(queries)}: {query}",
                    (q_idx / len(queries)) * 0.5
                )

            # 3. Loop through pages
            for page in range(1, max_pages_per_query + 1):
                if is_stopped():
                    break

                if summary["unique_leads_saved"] >= target_count:
                    logger.info(f"Target count reached: {target_count}")
                    break

                results = fetch_serper_results(query, page=page)

                if not results:
                    break

                summary["raw_results_found"] += len(results)
                summary["pages_processed"] += 1

                # Update job stats in DB for scraping count
                job_repo.update_status(
                    job_id,
                    "RUNNING",
                    total_scraped=summary["raw_results_found"]
                )

                # 4. Clean and Dedupe CURRENT page results
                unique_page_results = dedupe_serp_results(results)

                # 5. Process and Save Leads IMMEDIATELY
                for res in unique_page_results:
                    if is_stopped():
                        break

                    if summary["unique_leads_saved"] >= target_count:
                        logger.info(f"Target count reached: {target_count}")
                        break

                    title = res.get("title", "Unknown Business")
                    link = res.get("link", "")

                    if not link:
                        _save_raw_record(db, job_id, campaign_id, title, link, None, None, location, main_query, page, res, "INVALID_URL", "Missing link")
                        continue

                    if link in seen_urls:
                        _save_raw_record(db, job_id, campaign_id, title, link, None, None, location, main_query, page, res, "DUPLICATE", "Duplicate URL in this run")
                        continue

                    seen_urls.add(link)
                    snippet = res.get("snippet", "")
                    domain = get_domain(link)

                    is_irrelevant = res.get("is_irrelevant", False)
                    is_dir = res.get("is_directory", False)
                    is_soc = res.get("is_social", False)

                    # ----------------------------------------------------
                    # Duplicate protection by domain
                    # ----------------------------------------------------
                    # Only apply this to normal business websites.
                    # Do NOT apply domain dedupe to directory/social sites,
                    # because Yelp/Opencare/Facebook/Instagram can contain
                    # multiple real businesses under the same domain.
                    if domain and not is_dir and not is_soc and not is_irrelevant:
                        if domain in seen_business_domains:
                            summary["total_duplicates"] += 1
                            job_repo.update_status(
                                job_id,
                                "RUNNING",
                                total_duplicates=summary["total_duplicates"]
                            )
                            logger.info(f"Skipped duplicate business domain: {domain}")
                            _save_raw_record(db, job_id, campaign_id, title, link, None, None, location, main_query, page, res, "DUPLICATE", f"Duplicate business domain: {domain}")
                            continue

                    lead_hash = build_lead_hash(
                        business_name=title,
                        website=link,
                        location=main_query,
                        domain=domain,
                    )

                    # Check DB duplicate by existing lead hash
                    if lead_repo.check_duplicate(lead_hash=lead_hash):
                        summary["total_duplicates"] += 1

                        job_repo.update_status(
                            job_id,
                            "RUNNING",
                            total_duplicates=summary["total_duplicates"]
                        )

                        logger.debug(f"Lead already exists: {title}")
                        _save_raw_record(db, job_id, campaign_id, title, link, None, None, location, main_query, page, res, "ALREADY_EXISTS", "Lead hash exists in DB")
                        continue

                    # Also check business-level hash for normal business websites
                    # This prevents:
                    # abcclinic.com/page-1
                    # abcclinic.com/page-2
                    # from being saved as separate leads.
                    if domain and not is_dir and not is_soc and not is_irrelevant:
                        business_hash = generate_business_hash(title, domain, main_query)

                        if lead_repo.check_duplicate(lead_hash=business_hash):
                            summary["total_duplicates"] += 1

                            job_repo.update_status(
                                job_id,
                                "RUNNING",
                                total_duplicates=summary["total_duplicates"]
                            )

                            logger.debug(f"Business already exists by domain hash: {title} | {domain}")
                            _save_raw_record(db, job_id, campaign_id, title, link, None, None, location, main_query, page, res, "ALREADY_EXISTS", "Business hash exists in DB")
                            continue

                    # Extract phones/emails from SERP snippet as fallback
                    snippet_contact = extract_contact_from_snippet(
                        snippet,
                        default_region=phone_region
                    )

                    contact_info = {
                        "emails": snippet_contact.get("emails", []),
                        "phones": snippet_contact.get("phones", []),
                        "whatsapp_links": [],
                        "social_links": [],
                        "contact_page": "",
                        "website_status": "snippet_fallback",
                        "scraped_text_snippet": snippet
                    }

                    # 6. Scrape Website Enrichment
                    if not scrape_websites:
                        contact_info["website_status"] = "skipped_by_user"

                    elif is_irrelevant:
                        contact_info["website_status"] = "skipped_irrelevant_domain"

                    elif is_dir or is_soc:
                        contact_info["website_status"] = "skipped_directory_or_social"

                    else:
                        logger.info(f"Scraping website: {link}")

                        website_contact_info = scrape_contact_info(link)

                        if not isinstance(website_contact_info, dict):
                            logger.warning(f"Unexpected response type from scrape_contact_info. Expected dict, got {type(website_contact_info)}")
                            website_contact_info = {}

                        # Merge snippet fallback + website results
                        contact_info["emails"] = list(set(
                            contact_info["emails"] + website_contact_info.get("emails", [])
                        ))

                        merged_phones = (
                            contact_info["phones"] +
                            website_contact_info.get("phones", [])
                        )

                        contact_info["phones"] = clean_phone_list(
                            merged_phones,
                            default_region=phone_region
                        )

                        contact_info["social_links"] = list(set(
                            contact_info["social_links"] + website_contact_info.get("social_links", [])
                        ))

                        contact_info["whatsapp_links"] = list(set(
                            contact_info["whatsapp_links"] + website_contact_info.get("whatsapp_links", [])
                        ))

                        contact_info["contact_page"] = website_contact_info.get("contact_page", "")
                        contact_info["website_status"] = website_contact_info.get("website_status", "error")

                        if website_contact_info.get("scraped_text_snippet"):
                            contact_info["scraped_text_snippet"] = website_contact_info["scraped_text_snippet"]

                        time.sleep(0.5)

                    # Final phone cleanup even if website was skipped
                    contact_info["phones"] = clean_phone_list(
                        contact_info.get("phones", []),
                        default_region=phone_region
                    )

                    # 7. Prepare and Save
                    email = contact_info["emails"][0] if contact_info.get("emails") else None
                    phone = contact_info["phones"][0] if contact_info.get("phones") else None

                    # ----------------------------------------------------
                    # Duplicate protection by contact
                    # ----------------------------------------------------
                    # If same email/phone appears again, skip it.
                    # This handles cases where same business appears with
                    # different pages/titles but same contact details.
                    contact_key = build_contact_key(email, phone)

                    if contact_key and contact_key in seen_contact_keys:
                        summary["total_duplicates"] += 1
                        job_repo.update_status(
                            job_id,
                            "RUNNING",
                            total_duplicates=summary["total_duplicates"]
                        )
                        logger.info(f"Skipped duplicate contact: {title}")
                        _save_raw_record(db, job_id, campaign_id, title, link, email, phone, location, main_query, page, res, "DUPLICATE", "Duplicate contact email/phone in this run")
                        continue

                    # ----------------------------------------------------
                    # Dork Optimizer URL Exclusions Filter
                    # ----------------------------------------------------
                    from modules.dork_optimizer.dork_filters import is_low_quality_dork_url
                    website_url = link
                    if website_url and is_low_quality_dork_url(website_url, exclude_directories=True):
                        logger.info(f"Skipping low quality dork URL: {website_url}")
                        _save_raw_record(db, job_id, campaign_id, title, link, email, phone, location, main_query, page, res, "LOW_QUALITY", "Directory/News/Blog/PDF filtered by Dork Optimizer")
                        continue

                    has_name = bool(title)
                    has_phone = bool(phone)
                    has_email = bool(email)
                    has_website = bool(link)
                    has_address = bool(location)

                    if has_name and (has_phone or has_email or has_website or has_address):
                        # For normal business websites, save business-level hash.
                        # For directory/social URLs, keep URL-level hash because
                        # many businesses can live under same platform domain.
                        final_lead_hash = lead_hash

                        if domain and not is_dir and not is_soc and not is_irrelevant:
                            final_lead_hash = generate_business_hash(title, domain, main_query)

                        # ----------------------------------------------------
                        # Dork Optimizer Quality Scoring & Database Linkages
                        # ----------------------------------------------------
                        from modules.dork_optimizer.dork_filters import calculate_lead_quality_score
                        
                        lead_quality_score = calculate_lead_quality_score({
                            "website": link,
                            "email": email,
                            "phone": phone,
                            "business_name": title,
                            "category": main_query,
                            "source": "serper_bulk_dork"
                        })
                        
                        # Find matching GeneratedDork to link original metadata
                        dork_type = None
                        opportunity_id = None
                        try:
                            from modules.database.models import GeneratedDork as G_Dork
                            d_record = db.query(G_Dork).filter(G_Dork.dork == main_query).first()
                            if d_record:
                                dork_type = d_record.dork_type
                                opportunity_id = d_record.opportunity_id
                        except Exception:
                            pass

                        lead_data = {
                            "campaign_id": campaign_id,
                            "scraping_job_id": job_id,
                            "business_name": title,
                            "category": main_query,
                            "phone": phone,
                            "email": email,
                            "website": link,
                            "address": location,
                            "source": "serper_bulk_dork",  # Mark dork scraper origin
                            "lead_hash": final_lead_hash,
                            "has_email": has_email,
                            "has_phone": has_phone,
                            "has_website": has_website,
                            "rating": safe_float(res.get("rating")),
                            "reviews_count": safe_int(res.get("ratingCount") or res.get("reviews") or res.get("reviewsCount")),
                            "raw_data": {
                                **res,
                                **contact_info,
                                "dork_quality_score": lead_quality_score,
                                "original_dork": main_query,
                                "source": "dork_optimizer",
                                "dork_type": dork_type,
                                "opportunity_id": opportunity_id
                            }
                        }

                        try:
                            lead_repo.create(**lead_data)

                            summary["unique_leads_saved"] += 1

                            if email:
                                summary["emails_found"] += 1

                            if phone:
                                summary["phones_found"] += 1

                            # Mark domain/contact as seen only after successful save.
                            # This avoids losing data if DB save fails.
                            if domain and not is_dir and not is_soc and not is_irrelevant:
                                seen_business_domains.add(domain)

                            if contact_key:
                                seen_contact_keys.add(contact_key)

                            # Update job stats in DB real-time for saved count
                            job_repo.update_status(
                                job_id,
                                "RUNNING",
                                total_saved=summary["unique_leads_saved"]
                            )

                            logger.info(f"✅ Saved Lead ({summary['unique_leads_saved']}): {title}")
                            _save_raw_record(db, job_id, campaign_id, title, link, email, phone, location, main_query, page, res, "SAVED_LEAD", "Successfully saved lead")

                        except Exception as e:
                            logger.error(f"❌ DATABASE SAVE FAILED for {title}: {str(e)}")
                            summary["errors"].append(f"Save error: {title}")
                            _save_raw_record(db, job_id, campaign_id, title, link, email, phone, location, main_query, page, res, "FAILED", f"DB Save Error: {e}")

                    else:
                        logger.warning(f"⚠️ Skipped lead {title}: Missing contact info.")
                        status = "FILTERED"
                        if not has_email: status = "MISSING_EMAIL"
                        elif not has_phone: status = "MISSING_PHONE"
                        _save_raw_record(db, job_id, campaign_id, title, link, email, phone, location, main_query, page, res, status, "Missing contact info")

                time.sleep(1)

            summary["queries_processed"] += 1

        if is_stopped():
            summary["status"] = "stopped"

            job_repo.update_status(
                job_id,
                "STOPPED",
                total_scraped=summary["raw_results_found"],
                total_saved=summary["unique_leads_saved"]
            )

        else:
            summary["status"] = "completed"

            job_repo.update_status(
                job_id,
                "COMPLETED",
                total_scraped=summary["raw_results_found"],
                total_saved=summary["unique_leads_saved"]
            )
            
        # Normalize counts
        db_norm = SessionLocal()
        try:
            j_norm = db_norm.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
            if j_norm:
                if not is_stopped():
                    from datetime import datetime
                    j_norm.completed_at = datetime.utcnow()
                scraped = j_norm.total_scraped or 0
                saved = j_norm.total_saved or 0
                duplicates = j_norm.total_duplicates or 0
                failed = j_norm.total_failed or 0
                accounted = saved + duplicates + failed
                if scraped > accounted:
                    duplicates += scraped - accounted
                    j_norm.total_duplicates = duplicates
                db_norm.commit()
        finally:
            db_norm.close()

    except Exception as e:
        logger.error(f"Bulk scraping failed: {str(e)}")

        summary["status"] = "failed"
        summary["errors"].append(str(e))

        job_repo.update_status(
            job_id,
            "FAILED",
            error_message=str(e)
        )

    return summary