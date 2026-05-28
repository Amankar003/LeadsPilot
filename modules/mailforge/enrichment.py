import os
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
import phonenumbers
from email_validator import validate_email, EmailNotValidError

from modules.mailforge.constants import (
    FREE_EMAIL_DOMAINS,
    EMAIL_TYPE_BUSINESS,
    EMAIL_TYPE_FREE,
    EMAIL_TYPE_INVALID,
    ENRICH_STATUS_ENRICHED,
    ENRICH_STATUS_PARTIAL,
    ENRICH_STATUS_FAILED,
    ENRICH_STATUS_NEEDS_REVIEW
)
from utils.logging_utils import get_logger

logger = get_logger(__name__)

EMAIL_COL_ALIASES = {"email", "email_address", "mail", "e-mail", "contact_email", "email id", "emailid"}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
}

class MailForgeEnricher:
    def enrich_email(self, email: str) -> dict:
        """
        Enrich a single email address according to MailForge requirements.
        """
        email = str(email).strip()
        result = {
            "email": email,
            "domain": "",
            "website": "",
            "business_name": "",
            "person_name": "",
            "phone": "",
            "social_links": {},
            "category": "",
            "confidence_score": 0.0,
            "enrichment_status": ENRICH_STATUS_FAILED,
            "notes": ""
        }

        # 1. Validate Email format
        try:
            val = validate_email(email)
            email_normalized = val.email
            domain = email_normalized.split("@")[-1].lower().strip()
            result["email"] = email_normalized
            result["domain"] = domain
        except EmailNotValidError as e:
            result["notes"] = f"Invalid email format: {e}"
            result["enrichment_status"] = ENRICH_STATUS_FAILED
            return result

        # 2. Try to infer receiver name from email prefix
        prefix = email_normalized.split("@")[0]
        person_name = prefix.replace(".", " ").replace("_", " ").replace("-", " ").title()
        if person_name in ["Info", "Contact", "Admin", "Support", "Office", "Sales", "Hello"]:
            person_name = "Business Owner"
        result["person_name"] = person_name

        # 3. Handle free email domains
        if domain in FREE_EMAIL_DOMAINS:
            result["confidence_score"] = 0.3
            result["enrichment_status"] = ENRICH_STATUS_NEEDS_REVIEW
            result["notes"] = "Free email domain detected. Manual review required."
            return result

        # 4. For business domains
        website = f"https://{domain}"
        result["website"] = website
        result["confidence_score"] = 0.5  # default baseline for inferred business website

        try:
            # Fetch homepage if possible
            r = requests.get(website, headers=HEADERS, timeout=8, allow_redirects=True)
            if r.status_code == 200:
                result["website"] = r.url  # use final redirected URL
                soup = BeautifulSoup(r.text, "html.parser")
                
                # Extract business name
                biz_name = ""
                og_site = soup.find("meta", property="og:site_name")
                if og_site and og_site.get("content"):
                    biz_name = og_site.get("content").strip()
                else:
                    og_title = soup.find("meta", property="og:title")
                    if og_title and og_title.get("content"):
                        biz_name = og_title.get("content").strip()
                    elif soup.title and soup.title.string:
                        biz_name = soup.title.string.strip()
                        # Clean common suffix
                        if " | " in biz_name:
                            biz_name = biz_name.split(" | ")[0]
                        elif " - " in biz_name:
                            biz_name = biz_name.split(" - ")[0]
                
                if not biz_name:
                    biz_name = domain.split(".")[0].capitalize()
                result["business_name"] = biz_name

                # Extract meta description as notes
                meta_desc = soup.find("meta", attrs={"name": "description"})
                if meta_desc and meta_desc.get("content"):
                    result["notes"] = meta_desc.get("content").strip()

                # Extract phone numbers
                phones = set()
                text_content = soup.get_text()
                # Simple phone regex matching
                raw_phones = re.findall(r"(\+?\d[\d\-\s\(\)\.]{8,}\d)", text_content)
                for raw in raw_phones:
                    cleaned = re.sub(r"\D", "", raw)
                    if 9 <= len(cleaned) <= 15:
                        phones.add(raw.strip())
                if phones:
                    # Try to parse the first one cleanly
                    try:
                        for p in phones:
                            parsed = phonenumbers.parse(p, None)
                            if phonenumbers.is_possible_number(parsed):
                                result["phone"] = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                                break
                        if not result["phone"]:
                            result["phone"] = list(phones)[0]
                    except:
                        result["phone"] = list(phones)[0]

                # Extract social links
                socials = {}
                for a in soup.find_all("a", href=True):
                    href = a["href"].lower()
                    if "facebook.com" in href:
                        socials["facebook"] = a["href"]
                    elif "instagram.com" in href:
                        socials["instagram"] = a["href"]
                    elif "linkedin.com" in href:
                        socials["linkedin"] = a["href"]
                    elif "twitter.com" in href or "x.com" in href:
                        socials["twitter"] = a["href"]
                    elif "youtube.com" in href:
                        socials["youtube"] = a["href"]
                result["social_links"] = socials

                # Successfully enriched
                result["enrichment_status"] = ENRICH_STATUS_ENRICHED
                result["confidence_score"] = 0.9
            else:
                result["enrichment_status"] = ENRICH_STATUS_PARTIAL
                result["notes"] = f"Domain answered with status code {r.status_code}. Details inferred."
                result["business_name"] = domain.split(".")[0].capitalize()

        except Exception as e:
            logger.warning(f"Failed to fetch homepage for {domain}: {e}")
            result["enrichment_status"] = ENRICH_STATUS_PARTIAL
            result["notes"] = f"Could not fetch website content: {e}. Details inferred."
            result["business_name"] = domain.split(".")[0].capitalize()

        return result

    def enrich_bulk_emails(self, emails: list[str]) -> list[dict]:
        """
        Enrich a list of email addresses.
        """
        enriched_list = []
        for email in emails:
            enriched_list.append(self.enrich_email(email))
        return enriched_list

    def enrich_uploaded_file(self, file_path: str) -> list[dict]:
        """
        Automatically load a CSV/Excel file, detect email column, and return enriched leads.
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return []

        try:
            if file_path.lower().endswith(".csv"):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return []

        # Auto-detect email column
        email_col = None
        for col in df.columns:
            col_lower = str(col).lower().strip().replace("_", "").replace("-", "")
            if col_lower in EMAIL_COL_ALIASES or "email" in col_lower:
                email_col = col
                break
        
        if email_col is None and len(df.columns) == 1:
            email_col = df.columns[0]

        if email_col is None:
            logger.error("No email column detected in file.")
            return []

        emails = df[email_col].astype(str).dropna().str.strip().tolist()
        emails = [e for e in emails if e and "@" in e]
        
        # Enrich detected emails
        enriched_results = []
        for idx, email in enumerate(emails):
            enriched = self.enrich_email(email)
            # Merge any other columns present in the row if business name/phone is missing
            try:
                row_data = df.iloc[idx].to_dict()
                # Guess business name from other columns if not enriched
                if not enriched["business_name"]:
                    for key in ["businessname", "company", "organization", "name"]:
                        for r_key in row_data.keys():
                            if key in r_key.lower().replace("_", ""):
                                enriched["business_name"] = str(row_data[r_key]).strip()
                                break
                # Guess phone if not enriched
                if not enriched["phone"]:
                    for key in ["phone", "tel", "mobile", "contact"]:
                        for r_key in row_data.keys():
                            if key in r_key.lower().replace("_", ""):
                                enriched["phone"] = str(row_data[r_key]).strip()
                                break
            except:
                pass
            enriched_results.append(enriched)
            
        return enriched_results
