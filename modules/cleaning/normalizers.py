import re
import urllib.parse

def clean_business_name(name: str) -> str:
    if not name:
        return ""
    # Remove extra spaces, newlines
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def normalize_phone(phone: str) -> str:
    if not phone:
        return None
    # Remove all non-numeric characters except +
    cleaned = re.sub(r'[^\d+]', '', phone)
    return cleaned if cleaned else None

def normalize_website(url: str) -> str:
    if not url:
        return None
    url = url.strip()
    if not url.startswith('http'):
        url = 'https://' + url
    
    # Parse and clean
    try:
        parsed = urllib.parse.urlparse(url)
        # Remove trailing slashes and normalize
        netloc = parsed.netloc.lower()
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        return f"{parsed.scheme}://{netloc}{parsed.path}".rstrip('/')
    except Exception:
        return url
        
def clean_email(email: str) -> str:
    if not email:
        return None
    return email.lower().strip()
