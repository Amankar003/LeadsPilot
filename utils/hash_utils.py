import hashlib
import re

def normalize_email(email: str) -> str:
    """Normalize email address to lowercase and strip whitespace."""
    if not email:
        return ""
    return str(email).lower().strip()

def normalize_website(website: str) -> str:
    """Normalize website URI to include scheme and strip trailing parts."""
    if not website:
        return ""
    web = str(website).lower().strip()
    if not (web.startswith("http://") or web.startswith("https://")):
        web = "https://" + web
    return web

def extract_domain(email_or_website: str) -> str:
    """Extract a clean domain name from an email address or website URL."""
    if not email_or_website:
        return ""
    text = str(email_or_website).lower().strip()
    if '@' in text:
        return text.split('@')[-1].strip()
    
    # Otherwise treat as website
    domain = text
    if "://" in domain:
        domain = domain.split("://", 1)[1]
    if domain.startswith("www."):
        domain = domain[4:]
    # Strip paths, queries, ports
    domain = domain.split("/", 1)[0]
    domain = domain.split("?", 1)[0]
    domain = domain.split(":", 1)[0]
    return domain.strip()

def extract_details_from_email(email_str: str) -> dict:
    """
    Extract domain, website, and business name from email if confident.
    Sets business_name to domain-based title case.
    """
    if not email_str or '@' not in email_str:
        return {}
    
    try:
        local_part, domain = email_str.split('@', 1)
        domain = domain.lower().strip()
        
        # Generic public email providers to skip business details for
        generic_domains = {
            'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 
            'aol.com', 'icloud.com', 'zoho.com', 'protonmail.com', 
            'mail.com', 'yandex.com', 'gmx.com', 'live.com'
        }
        
        if domain in generic_domains:
            return {
                "email": email_str,
                "domain": domain,
                "website": None,
                "business_name": None
            }
            
        website = f"https://{domain}"
        
        # Extract business name from domain by dropping extensions and formatting
        name_part = domain
        dots = name_part.split('.')
        if len(dots) > 1:
            # Common extensions to drop
            extensions = {
                'com', 'org', 'net', 'edu', 'gov', 'co', 'ac', 'ae', 
                'uk', 'in', 'us', 'io', 'ai', 'info', 'biz', 'ca', 'au'
            }
            clean_parts = [p for p in dots if p not in extensions]
            if clean_parts:
                name_part = clean_parts[0]
            else:
                name_part = dots[0]
                
        name_part = name_part.replace('-', ' ').replace('_', ' ')
        business_name = name_part.title()
        
        return {
            "email": email_str,
            "domain": domain,
            "website": website,
            "business_name": business_name
        }
    except Exception:
        return {}

def generate_lead_hash(business_name: str = None, phone: str = None, website: str = None, location: str = None, email: str = None, domain: str = None, country: str = None, city: str = None) -> str:
    """
    Generates a prioritized, stable unique hash for a lead based on normalized fields.
    Priority:
      1. email
      2. website/domain
      3. phone
      4. business_name + city + country
      5. business_name
      
    Raises ValueError if all fields are empty or only contain weak data.
    """
    # Normalize inputs
    norm_email = normalize_email(email)
    
    norm_dom = domain.lower().strip() if domain else ""
    if not norm_dom and website:
        norm_dom = extract_domain(website)
    if not norm_dom and email:
        norm_dom = extract_domain(email)
        
    norm_web = normalize_website(website)
    norm_phone = re.sub(r'\D', '', str(phone)) if phone else ""
    
    norm_bname = str(business_name).lower().strip() if business_name else ""
    # Treat placeholder name as empty
    if norm_bname in {"", "unknown business", "nan", "none"}:
        norm_bname = ""
        
    norm_city = str(city or location or "").lower().strip()
    norm_country = str(country or "").lower().strip()
    
    # Check priority chain
    if norm_email:
        combined = f"email:{norm_email}"
    elif norm_dom:
        combined = f"domain:{norm_dom}"
    elif norm_web:
        combined = f"website:{norm_web}"
    elif norm_phone:
        combined = f"phone:{norm_phone}"
    elif norm_bname and (norm_city or norm_country):
        combined = f"business:{norm_bname}|{norm_city}|{norm_country}"
    elif norm_bname:
        combined = f"business:{norm_bname}"
    else:
        raise ValueError("Cannot generate lead hash from empty or weak fields.")
        
    return hashlib.md5(combined.encode('utf-8')).hexdigest()
