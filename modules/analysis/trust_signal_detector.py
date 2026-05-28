"""
trust_signal_detector.py - Detects trust-building elements on a website.
"""
from bs4 import BeautifulSoup
import re
from utils.logging_utils import get_logger

logger = get_logger(__name__)

def audit_trust_signals(html: str) -> dict:
    """
    Detect trust signals such as testimonials, privacy policies, etc.
    """
    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text(separator=" ", strip=True).lower()
    
    result = {
        "has_testimonials": False,
        "has_reviews": False,
        "has_portfolio": False,
        "has_about_page": False,
        "has_services_page": False,
        "has_privacy_policy": False,
        "has_terms": False,
        "has_google_maps_embed": False,
        "has_awards_certifications": False,
        "issues": []
    }
    
    # Check links
    for a in soup.find_all('a', href=True):
        href = a['href'].lower()
        text = a.get_text(strip=True).lower()
        
        if 'about' in href or 'about' in text:
            result["has_about_page"] = True
        elif 'service' in href or 'service' in text:
            result["has_services_page"] = True
        elif 'privacy' in href or 'privacy' in text:
            result["has_privacy_policy"] = True
        elif 'terms' in href or 'conditions' in text:
            result["has_terms"] = True
        elif 'portfolio' in href or 'gallery' in href or 'portfolio' in text:
            result["has_portfolio"] = True
            
    # Keywords in text
    if any(word in page_text for word in ["testimonial", "what our clients say", "what our customers say", "success stories"]):
        result["has_testimonials"] = True
        
    if any(word in page_text for word in ["review", "rated 5 stars", "google reviews"]):
        result["has_reviews"] = True
        
    if any(word in page_text for word in ["award", "certified", "accreditation", "partner"]):
        result["has_awards_certifications"] = True
        
    # Iframes (Google Maps)
    for iframe in soup.find_all('iframe'):
        src = iframe.get('src', '').lower()
        if 'google.com/maps' in src:
            result["has_google_maps_embed"] = True
            break
            
    if not result["has_privacy_policy"]:
        result["issues"].append("No Privacy Policy link found (may be required by law like GDPR/CCPA).")
        
    if not result["has_testimonials"] and not result["has_reviews"]:
        result["issues"].append("No visible testimonials or reviews found (missing social proof).")
        
    if not result["has_about_page"]:
        result["issues"].append("No 'About' page link found (reduces trust).")

    return result
