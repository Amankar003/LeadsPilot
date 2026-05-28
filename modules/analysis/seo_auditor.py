"""
seo_auditor.py — Audits a website's basic and technical SEO signals.
Checks title, meta description, headings, canonical, robots.txt, sitemap,
Open Graph, Schema markup, image alts, word count, and local SEO indicators.
"""
import re
import httpx
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from utils.logging_utils import get_logger

logger = get_logger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _fetch_text(url: str, timeout: float = 10.0) -> tuple:
    """Fetch URL, return (status_code, text, error)."""
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=timeout, follow_redirects=True)
        return resp.status_code, resp.text, None
    except Exception as e:
        return 0, "", str(e)


def audit_seo(html: str, url: str) -> dict:
    """
    Run SEO audit on pre-fetched HTML content.

    Returns structured dict with all SEO signals.
    """
    soup = BeautifulSoup(html, "html.parser")
    base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

    result = {
        "title": "",
        "title_length": 0,
        "title_present": False,
        "title_good_length": False,
        "meta_description": "",
        "meta_description_length": 0,
        "meta_description_present": False,
        "meta_description_good_length": False,
        "h1_count": 0,
        "h1_texts": [],
        "h2_count": 0,
        "h2_texts": [],
        "canonical_tag": "",
        "canonical_present": False,
        "robots_txt_accessible": False,
        "robots_txt_url": "",
        "sitemap_accessible": False,
        "sitemap_url": "",
        "og_tags": {},
        "og_present": False,
        "twitter_card_present": False,
        "schema_markup_present": False,
        "schema_types": [],
        "total_images": 0,
        "images_with_alt": 0,
        "images_without_alt": 0,
        "alt_tag_percentage": 0,
        "word_count": 0,
        "noindex": False,
        "nofollow": False,
        "local_seo_signals": {
            "phone_visible": False,
            "address_visible": False,
            "city_mentioned": False,
        },
    }

    # ── Title ──
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        result["title"] = title_tag.string.strip()
        result["title_length"] = len(result["title"])
        result["title_present"] = True
        result["title_good_length"] = 30 <= len(result["title"]) <= 65

    # ── Meta Description ──
    meta_desc = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
    if meta_desc and meta_desc.get("content"):
        result["meta_description"] = meta_desc["content"].strip()
        result["meta_description_length"] = len(result["meta_description"])
        result["meta_description_present"] = True
        result["meta_description_good_length"] = 120 <= len(result["meta_description"]) <= 160

    # ── Headings ──
    h1s = soup.find_all("h1")
    result["h1_count"] = len(h1s)
    result["h1_texts"] = [h.get_text(strip=True)[:100] for h in h1s[:5]]
    h2s = soup.find_all("h2")
    result["h2_count"] = len(h2s)
    result["h2_texts"] = [h.get_text(strip=True)[:100] for h in h2s[:10]]

    # ── Canonical ──
    canonical = soup.find("link", attrs={"rel": "canonical"})
    if canonical and canonical.get("href"):
        result["canonical_tag"] = canonical["href"]
        result["canonical_present"] = True

    # ── Robots Meta ──
    robots_meta = soup.find("meta", attrs={"name": re.compile(r"robots", re.I)})
    if robots_meta and robots_meta.get("content"):
        content = robots_meta["content"].lower()
        result["noindex"] = "noindex" in content
        result["nofollow"] = "nofollow" in content

    # ── Open Graph ──
    og_tags = soup.find_all("meta", attrs={"property": re.compile(r"^og:", re.I)})
    for tag in og_tags:
        prop = tag.get("property", "")
        val = tag.get("content", "")
        result["og_tags"][prop] = val
    result["og_present"] = len(og_tags) > 0

    # ── Twitter Card ──
    twitter_tags = soup.find_all("meta", attrs={"name": re.compile(r"^twitter:", re.I)})
    result["twitter_card_present"] = len(twitter_tags) > 0

    # ── Schema Markup ──
    schema_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    result["schema_markup_present"] = len(schema_scripts) > 0
    for script in schema_scripts[:5]:
        try:
            import json
            data = json.loads(script.string or "")
            if isinstance(data, dict) and "@type" in data:
                result["schema_types"].append(data["@type"])
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "@type" in item:
                        result["schema_types"].append(item["@type"])
        except Exception:
            pass

    # ── Images ──
    imgs = soup.find_all("img")
    result["total_images"] = len(imgs)
    result["images_with_alt"] = sum(1 for img in imgs if img.get("alt", "").strip())
    result["images_without_alt"] = result["total_images"] - result["images_with_alt"]
    result["alt_tag_percentage"] = (
        round(result["images_with_alt"] / result["total_images"] * 100, 1)
        if result["total_images"] > 0
        else 100
    )

    # ── Word Count ──
    text = soup.get_text(separator=" ", strip=True)
    words = [w for w in text.split() if len(w) > 1]
    result["word_count"] = len(words)

    # ── Local SEO Signals ──
    page_text = text.lower()
    phone_pattern = re.compile(
        r"(?:\+?\d{1,4}[\s\-.]?)?\(?\d{1,4}\)?[\s\-.]?\d{3,4}[\s\-.]?\d{3,4}"
    )
    if phone_pattern.search(page_text):
        result["local_seo_signals"]["phone_visible"] = True

    address_patterns = [
        r"\b\d+\s+\w+\s+(street|st|avenue|ave|road|rd|drive|dr|lane|ln|blvd|way)\b",
        r"\b(suite|unit|floor|building)\s*#?\s*\d+\b",
    ]
    for pat in address_patterns:
        if re.search(pat, page_text, re.I):
            result["local_seo_signals"]["address_visible"] = True
            break

    # ── Robots.txt ──
    robots_url = urljoin(base_url, "/robots.txt")
    result["robots_txt_url"] = robots_url
    try:
        code, _, _ = _fetch_text(robots_url, timeout=5)
        result["robots_txt_accessible"] = code == 200
    except Exception:
        pass

    # ── Sitemap ──
    sitemap_url = urljoin(base_url, "/sitemap.xml")
    result["sitemap_url"] = sitemap_url
    try:
        code, _, _ = _fetch_text(sitemap_url, timeout=5)
        result["sitemap_accessible"] = code == 200
    except Exception:
        pass

    return result
