"""
broken_link_checker.py — Checks homepage links for broken/dead references.
Scans limited number of internal/external links. HEAD first, GET fallback.
"""
import httpx
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from utils.logging_utils import get_logger

logger = get_logger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
}

MAX_LINKS_TO_CHECK = 20
TIMEOUT = 8.0


def _check_link(url: str) -> dict:
    """Check a single URL. HEAD first, GET fallback."""
    result = {"url": url, "status": 0, "ok": False, "is_redirect": False, "error": None}

    try:
        resp = httpx.head(
            url, headers=HEADERS, timeout=TIMEOUT,
            follow_redirects=True
        )
        result["status"] = resp.status_code
        result["ok"] = resp.status_code < 400
        result["is_redirect"] = len(resp.history) > 0
        return result
    except Exception:
        pass

    # HEAD failed — try GET (some servers block HEAD)
    try:
        resp = httpx.get(
            url, headers=HEADERS, timeout=TIMEOUT,
            follow_redirects=True
        )
        result["status"] = resp.status_code
        result["ok"] = resp.status_code < 400
        result["is_redirect"] = len(resp.history) > 0
    except httpx.TimeoutException:
        result["error"] = "timeout"
    except httpx.ConnectError as e:
        result["error"] = "unreachable"
    except Exception as e:
        result["error"] = str(e)[:100]

    return result


def audit_broken_links(html: str, url: str) -> dict:
    """
    Extract and check links from homepage HTML.
    Returns structured broken link report.
    """
    soup = BeautifulSoup(html, "html.parser")
    base_domain = urlparse(url).netloc.lower()

    result = {
        "total_links_found": 0,
        "links_checked": 0,
        "internal_links": 0,
        "external_links": 0,
        "broken_links": [],
        "broken_count": 0,
        "redirect_links": [],
        "redirect_count": 0,
        "timeout_links": [],
        "timeout_count": 0,
        "issues": [],
    }

    # ── Extract all <a> links ──
    all_links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()

        # Skip anchors, javascript, mailto, tel
        if href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
            continue

        # Resolve relative URLs
        full_url = urljoin(url, href)

        # Only check http/https
        if full_url.startswith(("http://", "https://")):
            all_links.add(full_url)

    result["total_links_found"] = len(all_links)

    # Separate internal vs external
    internal = []
    external = []
    for link in all_links:
        link_domain = urlparse(link).netloc.lower()
        if link_domain == base_domain or link_domain.endswith("." + base_domain):
            internal.append(link)
        else:
            external.append(link)

    result["internal_links"] = len(internal)
    result["external_links"] = len(external)

    # ── Check a limited set of links ──
    # Prioritize internal links, then external
    links_to_check = internal[:MAX_LINKS_TO_CHECK]
    remaining_slots = MAX_LINKS_TO_CHECK - len(links_to_check)
    if remaining_slots > 0:
        links_to_check.extend(external[:remaining_slots])

    result["links_checked"] = len(links_to_check)

    for link in links_to_check:
        check = _check_link(link)

        if check["error"] == "timeout":
            result["timeout_links"].append(link)
        elif not check["ok"]:
            result["broken_links"].append({
                "url": link,
                "status": check["status"],
                "error": check["error"],
            })
        elif check["is_redirect"]:
            result["redirect_links"].append(link)

    result["broken_count"] = len(result["broken_links"])
    result["redirect_count"] = len(result["redirect_links"])
    result["timeout_count"] = len(result["timeout_links"])

    # ── Issues ──
    if result["broken_count"] > 0:
        result["issues"].append(
            f"{result['broken_count']} broken link(s) found — damages SEO and user experience"
        )
    if result["timeout_count"] > 2:
        result["issues"].append(
            f"{result['timeout_count']} links timed out — may indicate server issues"
        )

    return result
