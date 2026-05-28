"""
responsive_auditor.py — Checks mobile-readiness signals from HTML source.
Detects viewport meta, media queries, fixed-width indicators, responsive CSS.
"""
import re
from bs4 import BeautifulSoup
from utils.logging_utils import get_logger

logger = get_logger(__name__)


def audit_responsive(html: str, url: str) -> dict:
    """
    Audit responsive/mobile-readiness from HTML source.
    """
    soup = BeautifulSoup(html, "html.parser")

    result = {
        "has_viewport_meta": False,
        "viewport_content": "",
        "has_media_queries": False,
        "media_query_count": 0,
        "has_responsive_framework": False,
        "framework_detected": "",
        "fixed_width_indicators": [],
        "mobile_friendly_score": 0,  # 0-100
        "issues": [],
    }

    # ── Viewport Meta Tag ──
    viewport = soup.find("meta", attrs={"name": re.compile(r"viewport", re.I)})
    if viewport and viewport.get("content"):
        result["has_viewport_meta"] = True
        result["viewport_content"] = viewport["content"]
    else:
        result["issues"].append("Missing viewport meta tag — page may not scale on mobile")

    # ── Media Queries in inline styles ──
    style_tags = soup.find_all("style")
    mq_count = 0
    for style in style_tags:
        if style.string:
            mqs = re.findall(r"@media\b", style.string, re.I)
            mq_count += len(mqs)

    # Check linked stylesheets (we can't fetch them, but note them)
    link_stylesheets = soup.find_all("link", attrs={"rel": "stylesheet"})

    result["has_media_queries"] = mq_count > 0
    result["media_query_count"] = mq_count

    # ── Responsive Framework Detection ──
    page_html = str(soup).lower()
    frameworks = {
        "Bootstrap": ["bootstrap", "col-md-", "col-sm-", "col-lg-", "container-fluid"],
        "Tailwind CSS": ["tailwindcss", "sm:", "md:", "lg:"],
        "Foundation": ["foundation", "small-", "medium-", "large-"],
        "Bulma": ["bulma", "is-mobile", "is-tablet"],
        "Materialize": ["materialize", "materializecss"],
    }
    for fw_name, indicators in frameworks.items():
        if any(ind in page_html for ind in indicators):
            result["has_responsive_framework"] = True
            result["framework_detected"] = fw_name
            break

    # ── Fixed Width Indicators ──
    # Check for elements with fixed pixel widths in inline styles
    elements_with_style = soup.find_all(attrs={"style": True})
    for el in elements_with_style[:100]:  # Limit scan
        style = el.get("style", "")
        # Check for large fixed widths
        width_match = re.search(r"width\s*:\s*(\d+)px", style)
        if width_match:
            w = int(width_match.group(1))
            if w > 960:
                tag = el.name
                result["fixed_width_indicators"].append(
                    f"<{tag}> has fixed width: {w}px"
                )

    # Check for table-based layouts (non-responsive pattern)
    tables = soup.find_all("table")
    layout_tables = [t for t in tables if not t.find_parent("table")]
    if len(layout_tables) > 2:
        result["fixed_width_indicators"].append(
            f"Found {len(layout_tables)} tables — possible table-based layout"
        )

    # ── Scoring ──
    score = 0
    if result["has_viewport_meta"]:
        score += 40
    if result["has_media_queries"] or result["has_responsive_framework"]:
        score += 30
    if len(link_stylesheets) > 0:
        score += 10  # External CSS likely has responsive rules
    if not result["fixed_width_indicators"]:
        score += 20
    else:
        score -= len(result["fixed_width_indicators"]) * 5

    result["mobile_friendly_score"] = max(0, min(100, score))

    if not result["has_viewport_meta"]:
        result["issues"].append("No viewport meta tag detected")
    if not result["has_media_queries"] and not result["has_responsive_framework"]:
        result["issues"].append("No media queries or responsive framework detected in inline styles")
    if result["fixed_width_indicators"]:
        result["issues"].append(f"{len(result['fixed_width_indicators'])} fixed-width layout element(s) detected")

    return result
