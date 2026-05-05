import re
from urllib.parse import urlparse

def get_domain(url: str) -> str:
    """Extracts domain from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except:
        return ""

def normalize_url(url: str) -> str:
    """Normalizes URL for deduplication."""
    try:
        parsed = urlparse(url)
        # Keep protocol, netloc, and path, remove query params and fragment
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if normalized.endswith("/"):
            normalized = normalized[:-1]
        return normalized.lower()
    except:
        return url.lower()

def is_social_url(url: str) -> bool:
    """Checks if the URL is a social media link."""
    social_domains = [
        'facebook.com', 'instagram.com', 'linkedin.com', 'youtube.com', 
        'twitter.com', 'x.com', 'pinterest.com', 'tiktok.com'
    ]
    domain = get_domain(url)
    return any(social in domain for social in social_domains)

def is_directory_url(url: str) -> bool:
    """Checks if the URL is a directory or marketplace."""
    directory_domains = [
        'justdial.com', 'sulekha.com', 'indiamart.com', 'practo.com',
        'zomato.com', 'swiggy.com', 'tripadvisor.com', 'magicbricks.com',
        '99acres.com', 'housing.com', 'yellowpages', 'yelp.com',
        'crunchbase.com', 'glassdoor.com', 'yell.com', 'checkatrade.com',
        'trustatrader.com', 'mybuilder.com', 'bark.com', 'houzz.com',
        'ratedpeople.com'
    ]
    domain = get_domain(url)
    return any(directory in domain for directory in directory_domains)

def is_informational_url(url: str) -> bool:
    """Checks if the URL is an informational or global site (non-lead)."""
    info_domains = [
        'wikipedia.org', 'wikipedia.com', 'britannica.com', 'dictionary.com', 
        'investopedia.com', 'mayoclinic.org', 'clevelandclinic.org',
        'webmd.com', 'healthline.com', 'medlineplus.gov', 'nih.gov', 'who.int',
        'researchgate.net', 'academia.edu', 'slideshare.net'
    ]
    domain = get_domain(url)
    return any(info in domain for info in info_domains)

def should_scrape_website(url: str) -> bool:
    """Determines if a website should be crawled for contact info."""
    if not url or not url.startswith('http'):
        return False
    
    # Skip PDFs and other non-html docs
    if any(url.lower().endswith(ext) for ext in ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx']):
        return False

    if is_social_url(url) or is_directory_url(url) or is_informational_url(url):
        return False
        
    return True

def is_valid_business_url(url: str) -> bool:
    """Basic check to see if it's a potential business website."""
    return should_scrape_website(url)

def dedupe_serp_results(results: list[dict]) -> list[dict]:
    """
    Dedupes results by URL and domain, preferring direct business sites 
    over directories if multiple appear for same business (heuristic).
    """
    if not results:
        return []

    # Map domain to result
    domain_map = {}
    url_map = {}
    
    unique_results = []
    
    for res in results:
        url = res.get("link", "")
        if not url:
            continue
            
        norm_url = normalize_url(url)
        domain = get_domain(url)
        
        # 1. Skip if URL seen
        if norm_url in url_map:
            continue
            
        is_dir = is_directory_url(url)
        is_soc = is_social_url(url)
        is_info = is_informational_url(url)
        
        res["domain"] = domain
        res["is_directory"] = is_dir
        res["is_social"] = is_soc
        res["is_informational"] = is_info
        
        if is_info:
            res["is_irrelevant"] = True
            res["irrelevant_reason"] = "informational_or_global_domain"
        
        # 2. Domain check logic
        # If we see a domain again, we only replace if current is NOT a directory/info and existing IS a directory/info
        if domain in domain_map:
            existing_idx = domain_map[domain]
            existing_res = unique_results[existing_idx]
            
            if not (is_dir or is_info) and (existing_res.get("is_directory") or existing_res.get("is_informational")):
                # Replace directory/info with direct site
                unique_results[existing_idx] = res
                url_map[norm_url] = True
            continue

        # 3. Add new unique domain/url
        unique_results.append(res)
        domain_map[domain] = len(unique_results) - 1
        url_map[norm_url] = True

    return unique_results
