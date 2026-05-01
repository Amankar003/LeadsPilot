import hashlib

def generate_lead_hash(business_name: str, phone: str, website: str, location: str) -> str:
    """Generate a unique hash for a lead based on core fields."""
    
    # Normalize inputs
    b_name = str(business_name).lower().strip() if business_name else ""
    p_num = str(phone).lower().strip() if phone else ""
    web = str(website).lower().strip() if website else ""
    loc = str(location).lower().strip() if location else ""
    
    # Create combined string
    combined = f"{b_name}|{p_num}|{web}|{loc}"
    
    # Return MD5 hash
    return hashlib.md5(combined.encode('utf-8')).hexdigest()
