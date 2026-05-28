import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# List of directory domains across target countries
DIRECTORY_DOMAINS = [
    "yelp.com", "yelp.co.uk", "yell.com", "checkatrade.com", "trustatrader.com",
    "justdial.com", "sulekha.com", "indiamart.com", "tradeindia.com",
    "bayut.com", "propertyfinder.ae", "dubizzle.com", "yellowpages.com",
    "angi.com", "thumbtack.com", "tripadvisor.com", "foursquare.com", "groupon.com"
]

# Social media and media hosting platforms
SOCIAL_DOMAINS = [
    "facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com",
    "youtube.com", "vimeo.com", "pinterest.com", "tiktok.com", "reddit.com", "quora.com"
]

# Blog and news signatures in URLs
BLOG_NEWS_SIGNATURES = [
    "/blog/", "/blogs/", "/news/", "/press/", "/articles/", "/category/blog",
    "/career", "/careers", "/jobs", "/hiring", "/recruitment", ".pdf", "/wiki/"
]

def is_low_quality_dork_url(url: str, exclude_directories: bool = True) -> bool:
    """
    Evaluates whether a scraped source URL is a noisy directory, blog, job post, PDF, or social page.
    """
    if not url:
        return True
        
    url_lower = url.lower().strip()
    
    # 1. Check directories
    if exclude_directories:
        if any(dir_domain in url_lower for dir_domain in DIRECTORY_DOMAINS):
            logger.info(f"Filtered out directory URL: {url}")
            return True
            
    # 2. Check jobs, careers, blogs, news, wikipedia, PDFs
    if any(sig in url_lower for sig in BLOG_NEWS_SIGNATURES):
        logger.info(f"Filtered out job/blog/news/pdf URL: {url}")
        return True
        
    # 3. Check social platforms
    if any(soc in url_lower for soc in SOCIAL_DOMAINS):
        # Allow custom business websites even if they link to social, 
        # but filter out organic search results directly landing on social profiles.
        # Only reject if it is the root or main user page of a social platform.
        if url_lower.count("/") <= 3:
            logger.info(f"Filtered out social direct landing URL: {url}")
            return True
            
    return False

def calculate_lead_quality_score(lead_data: Dict[str, Any]) -> int:
    """
    Calculates a digital maturity and contact validation score (0 to 100) for a scraped lead.
    """
    score = 0
    
    # 1. Custom Website Present (+20 points)
    website = lead_data.get("website")
    if website and "google.com" not in website.lower():
        score += 20
        
    # 2. Email Address Present (+30 points)
    email = lead_data.get("email")
    if email:
        score += 30
        
    # 3. Phone Number Present (+25 points)
    phone = lead_data.get("phone")
    if phone:
        score += 25
        
    # 4. Valid Business-like Title (+15 points)
    title = lead_data.get("business_name")
    if title and len(title) > 3 and not title.lower().startswith("unknown"):
        score += 15
        
    # 5. Targeted Category/Keywords Match (+10 points)
    category = lead_data.get("category", "")
    source = lead_data.get("source", "")
    if category or "dork" in source.lower():
        score += 10
        
    return min(score, 100)
