"""
LLM-1 — Trend Analyzer.

Takes today's fresh source data, sends to Gemini, returns structured trends.
"""

from modules.dork_optimizer.utils import call_llm, extract_json_from_response, TREND_MODEL, SERVICES_LIST
from modules.dork_optimizer.services.market_filter import is_india_market

SYSTEM_PROMPT = """You are a B2B market intelligence analyst for 3FI Tech, a digital services agency.

Analyze raw source data and identify actionable B2B opportunities where businesses need digital services.

Rules:
- STRICT RULE: Do NOT output any India recommendations or Indian market opportunities. Completely skip them.
- ONLY output foreign market opportunities.
- Preferred markets: USA, UAE, UK, Canada, Australia, Singapore, Saudi Arabia, Qatar, Kuwait, Germany, Netherlands, France, New Zealand.
- Do NOT invent trends. Use only the provided source data.
- If data is weak or vague, lower the confidence_score.
- Country and region must come from the source data.
- Do not output duplicate trends.
- Maximum 20 trends.
- Output valid JSON object only (must start with {), no markdown, no explanation."""

# ── Max items to send to LLM (keeps prompt within token limits) ──
MAX_ITEMS_NORMAL = 20
MAX_ITEMS_RETRY = 10
MAX_FIELD_LENGTH = 200


def _truncate(text: str, max_len: int = MAX_FIELD_LENGTH) -> str:
    """Truncate a string to max_len characters."""
    if not text:
        return ""
    text = str(text).strip()
    return text[:max_len] if len(text) > max_len else text


def _prepare_source_text(source_items: list[dict], max_items: int) -> str:
    """Build a compact source text for the LLM prompt using only essential fields."""
    lines = []
    for i, item in enumerate(source_items[:max_items], 1):
        title = _truncate(item.get("title", ""))
        source = _truncate(item.get("source_name", ""), 50)
        source_type = _truncate(item.get("source_type", ""), 30)
        country = _truncate(item.get("country", ""), 50)
        region = _truncate(item.get("region", ""), 50)
        keyword = _truncate(item.get("keyword", ""), 80)
        # Only include a very short summary if available, skip raw_text entirely
        summary = _truncate(item.get("summary", ""), 120)

        lines.append(f"Source {i}:")
        if title:
            lines.append(f"  Title: {title}")
        if source or source_type:
            lines.append(f"  Source: {source} ({source_type})")
        if country:
            lines.append(f"  Country: {country}")
        if region:
            lines.append(f"  Region: {region}")
        if keyword:
            lines.append(f"  Keyword: {keyword}")
        if summary:
            lines.append(f"  Summary: {summary}")
        lines.append(f"  ID: {item.get('id', i)}")
        lines.append("")
    return "\n".join(lines)


def _build_prompt(source_text: str, item_count: int) -> str:
    """Build the LLM prompt."""
    services_str = ", ".join(SERVICES_LIST)
    return f"""Analyze these {item_count} raw market signals and identify up to 20 B2B campaign opportunities for 3FI Tech.

CRITICAL DIRECTIVE: Do NOT output any opportunities for the India market. Only focus on foreign markets.
Preferred foreign markets to target: USA, UAE, UK, Canada, Australia, Singapore, Saudi Arabia, Qatar, Kuwait, Germany, Netherlands, France, New Zealand.

3FI Tech services: {services_str}

SOURCE DATA:
{source_text}

Return a JSON object ONLY with a "trends" key containing the list of campaign opportunities:
{{
  "trends": [
    {{
      "trend_name": "Short descriptive trend title",
      "category": "tourism / real estate / healthcare / ecommerce / ai digital transformation / manufacturing / education / b2b services",
      "description": "Summary of the market signal and why businesses in this sector need help",
      "opportunity_score": 75,
      "business_impact": "How this directly impacts the target market's revenue or operations",
      "target_market": "The overarching target market (e.g., North American Healthcare)",
      "target_service": "One service from 3FI's list that fits best",
      "country": "Country from source data",
      "region": "City/region from source data"
    }}
  ]
}}

opportunity_score rules:
- 90-100: Multiple strong live sources confirm this trend
- 70-89: Clear signal from at least 1 source
- 50-69: Weak or indirect signal
- Below 50: Do not include"""


def _parse_llm_result(raw: str) -> list[dict]:
    """Parse the LLM response into a list of trend dicts."""
    result = extract_json_from_response(raw)

    if isinstance(result, list):
        return result[:20]
    elif isinstance(result, dict):
        if "error" in result:
            err_msg = result.get("error", "")
            print(f"[TrendAnalyzer] LLM returned error: {err_msg}")
            return []
        for key in ["trends", "opportunities", "analysis"]:
            if key in result and isinstance(result[key], list):
                return result[key][:20]
        return [result]
    return []


def _generate_deterministic_fallback(source_items: list[dict]) -> list[dict]:
    """Generate basic trend entries from source data without LLM — last-resort fallback."""
    from modules.dork_optimizer.services.market_filter import is_india_market

    # Simple sector detection keywords
    sector_keywords = {
        "tourism": ["tourism", "hotel", "travel", "resort", "hospitality"],
        "real estate": ["real estate", "property", "housing", "construction"],
        "healthcare": ["health", "medical", "clinic", "hospital", "dental"],
        "ecommerce": ["ecommerce", "e-commerce", "shopify", "online store", "retail"],
        "ai digital transformation": ["digital", "ai", "automation", "software", "tech"],
        "manufacturing": ["manufacturing", "factory", "industrial", "export"],
        "education": ["education", "training", "school", "university", "learning"],
        "b2b services": ["consulting", "services", "business", "agency"],
    }

    trends = []
    seen = set()
    for item in source_items[:MAX_ITEMS_NORMAL]:
        # Skip India items
        if is_india_market(item):
            continue

        country = (item.get("country") or "").strip()
        region = (item.get("region") or "").strip()
        title = (item.get("title") or "").strip()

        if not country or not title:
            continue

        # Skip India
        if country.lower() in ("india", "in", "bharat"):
            continue

        # Detect sector
        combined = f"{title} {item.get('keyword', '')}".lower()
        detected_sector = "b2b services"
        for sector, kws in sector_keywords.items():
            if any(kw in combined for kw in kws):
                detected_sector = sector
                break

        # Dedupe by country+sector
        key = f"{country.lower()}:{detected_sector}"
        if key in seen:
            continue
        seen.add(key)

        trends.append({
            "trend_name": _truncate(title, 100),
            "category": detected_sector,
            "description": f"Signal detected from live source data for {country}. Businesses in {detected_sector} may need digital services.",
            "opportunity_score": 55,
            "business_impact": "Potential efficiency gains and market reach expansion.",
            "target_market": f"{country} {detected_sector}",
            "target_service": "Website Development",
            "country": country,
            "region": region
        })

        if len(trends) >= 10:
            break

    print(f"[TrendAnalyzer] Deterministic fallback generated {len(trends)} trends")
    return trends


def _is_token_limit_error(error_str: str) -> bool:
    """Check if an error is a token/rate limit error that can be retried with fewer items."""
    indicators = ["413", "rate_limit", "tokens", "too large", "request too large", "tpm"]
    return any(ind in error_str.lower() for ind in indicators)


def analyze_trends(source_items: list[dict]) -> list[dict]:
    """
    LLM-1: Analyze fresh source data and return structured trends.

    Input: list of source_data dicts
    Output: list of trend analysis dicts

    Handles token limits gracefully with retry and deterministic fallback.
    """
    if not source_items:
        return []

    print(f"[TrendAnalyzer] Fresh items found: {len(source_items)}")

    # ── Attempt 1: Normal call with MAX_ITEMS_NORMAL items ──
    source_text = _prepare_source_text(source_items, MAX_ITEMS_NORMAL)
    prompt = _build_prompt(source_text, min(len(source_items), MAX_ITEMS_NORMAL))
    prompt_len = len(SYSTEM_PROMPT) + len(prompt)
    print(f"[TrendAnalyzer] Items sent to LLM: {min(len(source_items), MAX_ITEMS_NORMAL)}")
    print(f"[TrendAnalyzer] Approx prompt char length: {prompt_len}")

    try:
        raw = call_llm(prompt=prompt, system_prompt=SYSTEM_PROMPT, model=TREND_MODEL, temperature=0.2)
        trends = _parse_llm_result(raw)
        if trends:
            # Filter out any India trends that slipped through
            trends = [t for t in trends if not is_india_market(t)]
            print(f"[TrendAnalyzer] LLM returned {len(trends)} trends (attempt 1)")
            return trends
        # If LLM returned an error in JSON, check if it's a token limit
        if '"error"' in raw and _is_token_limit_error(raw):
            raise RuntimeError(f"Token limit error: {raw[:200]}")
        if trends == []:
            print("[TrendAnalyzer] LLM returned 0 trends, trying retry with fewer items...")
            raise RuntimeError("Empty result, retrying with fewer items")

    except Exception as e:
        err_str = str(e)
        print(f"[TrendAnalyzer] Attempt 1 failed: {err_str[:200]}")

        if _is_token_limit_error(err_str):
            # ── Attempt 2: Retry with fewer items ──
            print(f"[TrendAnalyzer] Token limit hit, retrying with {MAX_ITEMS_RETRY} items...")
            try:
                source_text = _prepare_source_text(source_items, MAX_ITEMS_RETRY)
                prompt = _build_prompt(source_text, min(len(source_items), MAX_ITEMS_RETRY))
                prompt_len = len(SYSTEM_PROMPT) + len(prompt)
                print(f"[TrendAnalyzer] Retry items sent: {min(len(source_items), MAX_ITEMS_RETRY)}")
                print(f"[TrendAnalyzer] Retry prompt char length: {prompt_len}")

                raw = call_llm(prompt=prompt, system_prompt=SYSTEM_PROMPT, model=TREND_MODEL, temperature=0.2)
                trends = _parse_llm_result(raw)
                if trends:
                    trends = [t for t in trends if not is_india_market(t)]
                    print(f"[TrendAnalyzer] LLM returned {len(trends)} trends (attempt 2 - retry)")
                    return trends
            except Exception as retry_e:
                print(f"[TrendAnalyzer] Retry also failed: {retry_e}")

    # ── Fallback: deterministic trends from source data ──
    print("[TrendAnalyzer] LLM failed, using deterministic fallback.")
    return _generate_deterministic_fallback(source_items)

class TrendAnalyzer:
    def __init__(self):
        pass
        
    def analyze_trends(self, source_items: list[dict], config: dict = None) -> list[dict]:
        """
        Wrapper to maintain compatibility with the service layer.
        Delegates to the module-level analyze_trends function.
        """
        return analyze_trends(source_items)
