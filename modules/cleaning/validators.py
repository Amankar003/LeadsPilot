from email_validator import validate_email, EmailNotValidError
import phonenumbers
import urllib.parse

def is_valid_email(email: str) -> bool:
    if not email:
        return False
    try:
        validate_email(email, check_deliverability=False)
        return True
    except EmailNotValidError:
        return False

def is_valid_phone(phone: str) -> bool:
    if not phone:
        return False
    try:
        # Assuming international format or parsing loosely
        parsed = phonenumbers.parse(phone, None)
        return phonenumbers.is_valid_number(parsed)
    except phonenumbers.NumberParseException:
        # If it fails to parse, we can still accept it if it looks like a phone (length/digits)
        # But for strictly valid:
        cleaned = ''.join(filter(str.isdigit, phone))
        return len(cleaned) >= 7

def is_valid_url(url: str) -> bool:
    if not url:
        return False
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False
