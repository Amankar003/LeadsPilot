"""
Market Filter — Shared helper to identify and filter out Indian market data.
"""

def is_india_market(item: dict) -> bool:
    """
    Check if a source, trend, or recommendation is related to the Indian market.

    Checks:
    - country is India, IN, Bharat (case-insensitive, ignoring whitespace)
    - region is Indian city (blocked list)
    - trend_name contains India or Indian
    - dorks contain site:.in or India
    """
    if not item or not isinstance(item, dict):
        return False

    blocked_countries = {"india", "in", "bharat"}
    blocked_cities = {
        "delhi", "new delhi", "mumbai", "bangalore", "bengaluru", "noida", "greater noida",
        "gurgaon", "gurugram", "pune", "hyderabad", "chennai", "kolkata", "ahmedabad",
        "jaipur", "lucknow", "surat", "kanpur", "nagpur", "indore", "bhopal", "patna",
        "vadodara", "ludhiana", "agra", "nashik", "faridabad", "meerut", "rajkot", "varanasi"
    }

    # 1. Check country field
    country = (item.get("country") or "").strip().lower()
    if country in blocked_countries:
        return True

    # 2. Check region field
    region = (item.get("region") or "").strip().lower()
    if region in blocked_cities:
        return True
    for city in blocked_cities:
        if city in region:
            return True

    # 3. Check trend_name field
    trend_name = (item.get("trend_name") or "").lower()
    if "india" in trend_name or "indian" in trend_name:
        return True

    # 4. Check dorks field — only check for site:.in (Indian domain)
    #    Do NOT check for the word "india" here because dorks legitimately
    #    contain "-india" as a negative exclusion filter (e.g. "-india -91").
    dorks = item.get("dorks")
    if dorks:
        if isinstance(dorks, list):
            for d in dorks:
                d_lower = str(d).lower()
                if "site:.in" in d_lower:
                    return True
        elif isinstance(dorks, str):
            d_lower = dorks.lower()
            if "site:.in" in d_lower:
                return True

    return False
