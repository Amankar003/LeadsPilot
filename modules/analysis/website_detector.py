"""
website_detector.py — Detects whether a lead has a reachable website.
Normalizes URLs, handles redirects, timeouts, SSL errors, and DNS failures.
"""
import re
import httpx
from urllib.parse import urlparse
from utils.logging_utils import get_logger

logger = get_logger(__name__)

# Common non-website patterns to filter out
NON_WEBSITE_PATTERNS = [
    r"facebook\.com", r"instagram\.com", r"linkedin\.com",
    r"twitter\.com", r"x\.com", r"youtube\.com",
    r"yelp\.com", r"tripadvisor\.com",
]


def normalize_url(url: str) -> str:
    """Clean and normalize a URL string."""
    if not url:
        return ""
    url = url.strip().rstrip("/")
    # Remove trailing punctuation
    url = re.sub(r"[.,;:!?]+$", "", url)
    if not url.startswith("http"):
        url = "https://" + url
    return url


def is_social_profile(url: str) -> bool:
    """Returns True if URL is a social media profile, not a business website."""
    lower = url.lower()
    return any(re.search(pat, lower) for pat in NON_WEBSITE_PATTERNS)


def detect_website(url_raw: str) -> dict:
    """
    Check if a lead's website is reachable and return structured result.

    Returns:
        {
            "has_website": bool,
            "original_url": str,
            "final_url": str,
            "status_code": int,
            "is_https": bool,
            "ssl_valid": bool,
            "redirect_chain": list,
            "load_time_ms": float,
            "page_size_bytes": int,
            "error": str or None,
            "error_type": str or None,  # dns/ssl/timeout/http_error/unreachable/invalid
        }
    """
    result = {
        "has_website": False,
        "original_url": url_raw or "",
        "final_url": "",
        "status_code": 0,
        "is_https": False,
        "ssl_valid": True,
        "redirect_chain": [],
        "load_time_ms": 0,
        "page_size_bytes": 0,
        "error": None,
        "error_type": None,
    }

    if not url_raw or not url_raw.strip():
        result["error"] = "No website URL provided"
        result["error_type"] = "missing"
        return result

    url = normalize_url(url_raw)
    result["original_url"] = url

    if is_social_profile(url):
        result["error"] = f"URL is a social media profile, not a business website: {url}"
        result["error_type"] = "social_profile"
        return result

    # Validate URL structure
    parsed = urlparse(url)
    if not parsed.netloc or "." not in parsed.netloc:
        result["error"] = f"Invalid URL structure: {url}"
        result["error_type"] = "invalid"
        return result

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    # Attempt HTTPS first, then HTTP fallback
    urls_to_try = [url]
    if url.startswith("https://"):
        urls_to_try.append(url.replace("https://", "http://", 1))
    elif url.startswith("http://"):
        urls_to_try = ["https://" + parsed.netloc + parsed.path] + urls_to_try

    for attempt_url in urls_to_try:
        try:
            import time
            start = time.time()
            with httpx.Client(
                follow_redirects=True,
                timeout=12.0,
                verify=True,
                headers=headers,
                max_redirects=10,
            ) as client:
                resp = client.get(attempt_url)

            elapsed_ms = (time.time() - start) * 1000
            result["final_url"] = str(resp.url)
            result["status_code"] = resp.status_code
            result["is_https"] = str(resp.url).startswith("https")
            result["load_time_ms"] = round(elapsed_ms, 1)
            result["page_size_bytes"] = len(resp.content)
            result["redirect_chain"] = [
                str(r.url) for r in resp.history
            ] if resp.history else []

            if resp.status_code < 400:
                result["has_website"] = True
                return result
            else:
                result["error"] = f"HTTP {resp.status_code}"
                result["error_type"] = "http_error"
                return result

        except httpx.ConnectError as e:
            err_str = str(e).lower()
            if "name" in err_str or "dns" in err_str or "getaddrinfo" in err_str:
                result["error"] = f"DNS resolution failed: {e}"
                result["error_type"] = "dns"
            else:
                result["error"] = f"Connection failed: {e}"
                result["error_type"] = "unreachable"
            continue

        except httpx.ConnectTimeout:
            result["error"] = "Connection timed out"
            result["error_type"] = "timeout"
            continue

        except httpx.ReadTimeout:
            result["error"] = "Read timed out (server too slow)"
            result["error_type"] = "timeout"
            # Server responded but too slow — site probably exists
            result["has_website"] = True
            return result

        except Exception as e:
            err_str = str(e).lower()
            if "ssl" in err_str or "certificate" in err_str:
                result["error"] = f"SSL certificate error: {e}"
                result["error_type"] = "ssl"
                result["ssl_valid"] = False
                # SSL error means site exists but has cert issues
                result["has_website"] = True
            else:
                result["error"] = f"Unexpected error: {e}"
                result["error_type"] = "unreachable"
            continue

    return result
