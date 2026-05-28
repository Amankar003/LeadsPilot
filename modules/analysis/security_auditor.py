"""
security_auditor.py — Checks basic security posture (non-invasive).
Looks for HTTPS, CSP, HSTS, X-Frame-Options, exposed Server headers.
"""
import httpx
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from utils.logging_utils import get_logger

logger = get_logger(__name__)

def audit_security(url: str, html: str = "") -> dict:
    """
    Perform non-invasive security checks based on headers and HTML content.
    """
    result = {
        "https_enabled": False,
        "hsts_enabled": False,
        "csp_enabled": False,
        "x_frame_options": False,
        "x_content_type": False,
        "referrer_policy": False,
        "server_exposed": False,
        "x_powered_by_exposed": False,
        "mixed_content_indicators": False,
        "issues": []
    }

    parsed = urlparse(url)
    result["https_enabled"] = parsed.scheme == "https"

    if not result["https_enabled"]:
        result["issues"].append("Site is not using HTTPS, data may be intercepted.")

    try:
        # Fetch just headers to check security headers
        resp = httpx.head(url, follow_redirects=True, timeout=8.0)
        headers = {k.lower(): v for k, v in resp.headers.items()}
        
        # HSTS
        if "strict-transport-security" in headers:
            result["hsts_enabled"] = True
        else:
            result["issues"].append("HSTS missing - site doesn't enforce HTTPS connections.")
            
        # CSP
        if "content-security-policy" in headers:
            result["csp_enabled"] = True
        else:
            result["issues"].append("Content-Security-Policy missing - vulnerable to XSS attacks.")
            
        # X-Frame-Options
        if "x-frame-options" in headers:
            result["x_frame_options"] = True
        else:
            result["issues"].append("X-Frame-Options missing - vulnerable to clickjacking.")
            
        # X-Content-Type-Options
        if "x-content-type-options" in headers:
            result["x_content_type"] = True
        else:
            result["issues"].append("X-Content-Type-Options missing - vulnerable to MIME sniffing.")
            
        # Referrer-Policy
        if "referrer-policy" in headers:
            result["referrer_policy"] = True
            
        # Information disclosure
        if "server" in headers:
            result["server_exposed"] = True
            
        if "x-powered-by" in headers:
            result["x_powered_by_exposed"] = True
            result["issues"].append(f"Technology stack exposed (X-Powered-By: {headers['x-powered-by']}).")
            
    except Exception as e:
        logger.warning(f"Failed to fetch headers for security audit on {url}: {e}")

    # Check for mixed content (HTTP links on HTTPS page)
    if result["https_enabled"] and html:
        soup = BeautifulSoup(html, "html.parser")
        http_resources = []
        
        for tag in soup.find_all(['img', 'script', 'link', 'iframe']):
            src = tag.get('src') or tag.get('href')
            if src and isinstance(src, str) and src.startswith("http://"):
                http_resources.append(src)
                
        if http_resources:
            result["mixed_content_indicators"] = True
            result["issues"].append(f"Mixed content found: {len(http_resources)} resource(s) loaded over insecure HTTP.")

    return result
