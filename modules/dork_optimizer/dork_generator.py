"""
LLM-2 — Dork Generator.

Takes one trend analysis item, generates practical keywords, dorks, URLs, and reasons.
"""

from modules.dork_optimizer.utils import call_llm, extract_json_from_response, DORK_MODEL
from modules.dork_optimizer.services.market_filter import is_india_market

SYSTEM_PROMPT = """You are a B2B lead generation expert for 3FI Tech.

Generate highly advanced Google search dorks for lead extraction, NOT simple/basic keyword searches.

Every single dork MUST include at least one advanced search operator (like site:, inurl:, intitle:, OR) or specific lead intent keywords (like "@gmail.com", "info@", "contact us", "WhatsApp", "Powered by Shopify", or country phone codes).

Strict Rules:
1. NEVER generate India leads. NEVER use site:.in or target India. Always append "-india -91" in the dorks to exclude Indian leads.
2. Every dork must include the noise filters: "-jobs -job -careers -hiring -recruitment -internship -pdf -gov -edu -org -news -press".
3. Avoid weak/generic dorks (e.g. "hotel dubai -jobs -careers" or "tourism UAE" is UNACCEPTABLE).
4. Output a valid JSON object ONLY containing: keywords, dorks, urls, why_this_dork, and opportunity_score.
5. All dorks should be highly specialized for specific lead-generation and email/contact extraction.
"""

# Map sectors to concrete search keywords
SECTOR_TO_KEYWORDS = {
    "ai digital transformation": [
        "software company", "IT services", "digital transformation consultant",
        "business automation", "CRM solutions", "ERP solutions",
        "technology consultant", "AI solutions", "IT consulting firm",
    ],
    "tourism": [
        "hotels", "homestays", "travel agencies", "tour operators",
        "guest houses", "restaurants", "resort", "travel agent",
    ],
    "real estate": [
        "real estate brokers", "property consultants", "property agents",
        "real estate companies", "real estate developers", "property dealers",
    ],
    "healthcare": [
        "clinics", "dental clinics", "skin clinics", "diagnostic centers",
        "medical centers", "hospitals", "physiotherapy center",
    ],
    "ecommerce": [
        "Shopify stores", "apparel stores", "beauty product stores",
        "furniture stores", "supplements stores", "online boutique",
    ],
    "manufacturing": [
        "manufacturers", "exporters", "suppliers",
        "industrial companies", "factories", "fabrication company",
    ],
    "wedding events": [
        "wedding venues", "wedding photographers", "event planners",
        "makeup artists", "destination wedding planners", "catering services",
    ],
    "education": [
        "training institute", "coaching center", "online course platform",
        "school", "college", "tutoring center",
    ],
    "b2b services": [
        "consulting firm", "business advisor", "accounting firm",
        "law firm", "recruitment agency", "marketing agency",
    ],
    "immigration": [
        "immigration consultant", "visa agent", "study abroad consultant",
        "overseas education consultant", "migration consultant",
    ],
}

# Country and domain metadata
COUNTRY_METADATA = {
    "usa": {
        "domains": ["site:.com"],
        "phone": "+1",
        "location_terms": ["USA", "United States"]
    },
    "united states": {
        "domains": ["site:.com"],
        "phone": "+1",
        "location_terms": ["USA", "United States"]
    },
    "canada": {
        "domains": ["site:.ca"],
        "phone": "+1",
        "location_terms": ["Canada"]
    },
    "uk": {
        "domains": ["site:.co.uk", "site:.uk"],
        "phone": "+44",
        "location_terms": ["UK", "London", "Manchester", "Edinburgh"]
    },
    "united kingdom": {
        "domains": ["site:.co.uk", "site:.uk"],
        "phone": "+44",
        "location_terms": ["UK", "London", "Manchester", "Edinburgh"]
    },
    "uae": {
        "domains": ["site:.ae"],
        "phone": "+971",
        "location_terms": ["UAE", "Dubai", "Abu Dhabi"]
    },
    "united arab emirates": {
        "domains": ["site:.ae"],
        "phone": "+971",
        "location_terms": ["UAE", "Dubai", "Abu Dhabi"]
    },
    "singapore": {
        "domains": ["site:.sg"],
        "phone": "+65",
        "location_terms": ["Singapore"]
    },
    "australia": {
        "domains": ["site:.com.au", "site:.au"],
        "phone": "+61",
        "location_terms": ["Australia"]
    },
    "germany": {
        "domains": ["site:.de"],
        "phone": "+49",
        "location_terms": ["Germany"]
    },
    "france": {
        "domains": ["site:.fr"],
        "phone": "+33",
        "location_terms": ["France"]
    },
    "netherlands": {
        "domains": ["site:.nl"],
        "phone": "+31",
        "location_terms": ["Netherlands"]
    },
    "qatar": {
        "domains": ["site:.qa"],
        "phone": "+974",
        "location_terms": ["Qatar"]
    },
    "new zealand": {
        "domains": ["site:.nz"],
        "phone": "+64",
        "location_terms": ["New Zealand"]
    },
    "saudi arabia": {
        "domains": ["site:.sa"],
        "phone": "+966",
        "location_terms": ["Saudi Arabia"]
    }
}


def resolve_country_metadata(country_str: str, region_str: str) -> dict:
    """Resolve site domain, phone code, and location terms for country metadata."""
    c_lower = (country_str or "").strip().lower()
    r_lower = (region_str or "").strip().lower()
    
    city_to_country = {
        "dubai": "uae",
        "abu dhabi": "uae",
        "london": "uk",
        "manchester": "uk",
        "edinburgh": "uk",
        "sydney": "australia",
        "melbourne": "australia",
        "toronto": "canada",
        "vancouver": "canada",
        "doha": "qatar",
        "riyadh": "saudi arabia",
        "jeddah": "saudi arabia"
    }
    
    resolved_country = None
    if r_lower in city_to_country:
        resolved_country = city_to_country[r_lower]
    elif c_lower in city_to_country:
        resolved_country = city_to_country[c_lower]
    elif c_lower in COUNTRY_METADATA:
        resolved_country = c_lower
    else:
        # Check substring matches
        for key in COUNTRY_METADATA:
            if key in c_lower or key in r_lower:
                resolved_country = key
                break
                
    if resolved_country and resolved_country in COUNTRY_METADATA:
        return COUNTRY_METADATA[resolved_country]
        
    # Default fallback for any other foreign countries (never India)
    return {
        "domains": ["site:.com"],
        "phone": "",
        "location_terms": [country_str or region_str or "global"]
    }


def get_location_mapping(country: str, region: str) -> dict:
    """Resolve site domain and phone code for the given country or region (legacy compatibility helper)."""
    meta = resolve_country_metadata(country, region)
    return {
        "site": meta["domains"][0] if meta["domains"] else "site:.com",
        "phone": meta["phone"],
        "default_region": meta["location_terms"][0]
    }


def is_acceptable_dork(dork: str) -> bool:
    """
    Permissive dork acceptor — only reject truly invalid dorks.

    A dork is accepted if:
    - It is a non-empty string
    - It does NOT target India (site:.in, "india", "indian")
    - It has at least one search operator OR intent keyword OR length > 10

    We intentionally do NOT reject for:
    - site:.com, quoted keywords, @gmail.com, info@
    - negative filters (-jobs, -careers, -pdf, -gov, -edu)
    - social URLs (facebook, linkedin)
    - generic contact terms, long query length
    """
    if not dork or not isinstance(dork, str):
        return False
    d_lower = dork.strip().lower()
    if not d_lower:
        return False
    # Hard reject: India-targeted dorks
    if "site:.in" in d_lower:
        return False
    if "india" in d_lower or "indian" in d_lower:
        return False
    # Accept if it has any useful operator or keyword
    useful_signals = [
        "site:", "inurl:", "intitle:", "@", "info", "contact",
        "email", "phone", "quote", "services",
    ]
    if any(sig in d_lower for sig in useful_signals):
        return True
    # Accept if length > 10 (non-trivial query)
    if len(d_lower) > 10:
        return True
    return False


# Legacy alias so any other code importing is_weak_dork still works
def is_weak_dork(dork: str) -> bool:
    """Legacy wrapper — returns the inverse of is_acceptable_dork."""
    return not is_acceptable_dork(dork)


def _clean_and_dedupe_dorks(dorks: list[str]) -> list[str]:
    """Simple cleanup: strip whitespace, remove empties, remove exact duplicates.
    
    No aggressive filtering — only reject India-targeted or truly empty dorks.
    """
    if not dorks:
        return []
    cleaned = []
    seen = set()
    for d in dorks:
        if not d:
            continue
        d_clean = " ".join(d.strip().split())
        if not d_clean:
            continue
        # Only reject India dorks
        d_lower = d_clean.lower()
        if "site:.in" in d_lower or "india" in d_lower or "indian" in d_lower:
            continue
        if d_lower not in seen:
            seen.add(d_lower)
            cleaned.append(d_clean)
    return cleaned


def generate_dorks_deterministically(keywords: list[str], country_meta: dict, location: str) -> list[str]:
    """Generate advanced B2B lead-generation Google dorks based on deterministic templates."""
    dorks = []
    
    if not keywords:
        keywords = ["business"]
        
    loc = location or country_meta["location_terms"][0]
    phone_code = country_meta["phone"] or "+1"
    domains = country_meta["domains"]
    domain = domains[0] if domains else "site:.com"
    
    for i, kw in enumerate(keywords[:10]):
        # A. Website contact dorks:
        dorks.append(f'{domain} "{loc}" "{kw}" inurl:contact "email" -india -91 -jobs -careers -pdf -gov -edu')
        
        # B. Gmail discovery:
        dorks.append(f'{domain} "{kw}" "{loc}" "@gmail.com" -india -91 -jobs -careers -pdf -gov -edu')
        
        # C. Info email:
        dorks.append(f'{domain} "{kw}" "{loc}" "info@" -india -91 -jobs -careers -pdf -gov -edu')
        
        # D. WhatsApp/contact:
        dorks.append(f'{domain} "{loc}" "{kw}" "WhatsApp" "contact" -india -91 -jobs -careers -pdf -gov -edu')
        
        # E. Phone code:
        dorks.append(f'{domain} "{kw}" "{loc}" "{phone_code}" "contact us" -india -91 -jobs -careers -pdf -gov -edu')
        
        # F. Shopify footprints:
        dorks.append(f'"Powered by Shopify" "{kw}" "{loc}" "{phone_code}" "info" -india -91 -jobs -careers -pdf -gov -edu')
        dorks.append(f'"Shopify" "{kw}" "{loc}" inurl:contact "@gmail.com" -india -91 -jobs -careers -pdf -gov -edu')
        
        # G. Facebook:
        dorks.append(f'site:facebook.com "About" "info" "{kw}" "{loc}" "{phone_code}" -india -91 -jobs -careers -pdf')
        
        # H. LinkedIn:
        dorks.append(f'site:linkedin.com/company "{kw}" "{loc}" "founder" -india -91 -jobs -careers')
        dorks.append(f'site:linkedin.com/in ("Founder" OR "CEO") "{kw}" "{loc}" -india -91 -jobs -careers')
        
        # I. Local service:
        alt_kw = keywords[(i + 1) % len(keywords)] if len(keywords) > 1 else kw
        dorks.append(f'{domain} ("{kw}" OR "{alt_kw}") "{loc}" "contact us" -india -91 -jobs -careers -pdf -gov -edu')

    return dorks


def deduplicate_dorks(dorks: list[str]) -> list[str]:
    """Remove duplicate dorks while preserving order (case-insensitive & whitespace-normalized)."""
    seen = set()
    unique = []
    for d in dorks:
        if not d:
            continue
        normalized = " ".join(d.lower().split())
        if normalized not in seen:
            seen.add(normalized)
            unique.append(d)
    return unique


def deduplicate_why_this_dork(why_list: list[dict]) -> list[dict]:
    """Remove duplicate why_this_dork entries by their dork string while preserving order."""
    seen = set()
    unique = []
    for item in why_list:
        if not isinstance(item, dict):
            continue
        d = item.get("dork", "")
        if not d:
            continue
        normalized = " ".join(d.lower().split())
        if normalized not in seen:
            seen.add(normalized)
            unique.append(item)
    return unique


def generate_dorks_for_trend(trend: dict) -> dict:
    """
    LLM-2: Generate keywords, dorks, URLs, and why-this-dork for one trend.

    Input: one trend analysis dict
    Output: dict with keywords, dorks, urls, why_this_dork, opportunity_score
    """
    import re, json
    if is_india_market(trend):
        print("[DorkGenerator] Skipping India market trend.")
        return {"skipped": True, "dorks": [], "why_this_dork": [], "keywords": [], "urls": [], "opportunity_score": 0}

    sector = (trend.get("sector") or "").lower()
    country = trend.get("country", "")
    region = trend.get("region", "")
    trend_name = trend.get("trend_name", "")
    recommended_service = trend.get("recommended_service", "")
    requirements = trend.get("business_requirements", [])

    # Get concrete keywords for this sector
    concrete_keywords = SECTOR_TO_KEYWORDS.get(sector, SECTOR_TO_KEYWORDS.get("b2b services", []))
    keywords_hint = ", ".join(concrete_keywords[:6])

    location = region if region else country

    # Resolve mapping
    country_meta = resolve_country_metadata(country, region)
    site_domain = country_meta["domains"][0] if country_meta["domains"] else "site:.com"
    phone_code = country_meta["phone"]
    # If phone code is missing, do not add phone code filter in deterministic dork generation

    prompt = f"""Generate 8-15 advanced Google search B2B business keywords and target website URLs for this opportunity.\n\nTrend: {trend_name}\nCountry: {country}\nRegion: {region}\nSector: {sector}\nBusiness Requirements: {', '.join(requirements) if requirements else 'general digital services'}\nRecommended Service: {recommended_service}\n\nConcrete business keywords to use: {keywords_hint}\nTarget Region/Location: {location}\nTarget Domain/Site Mapping to prioritize: {site_domain}\nTarget Phone Code to use: {phone_code}\n\nReturn ONLY valid JSON in this exact structure (no markdown, no explanation, no code block):\n{{\n  \"keywords\": [\"keyword1\", \"keyword2\", ...],\n  \"urls\": [\"https://example.com\"],\n  \"opportunity_score\": 85\n}}\n"""

    print("[DorkGenerator] LLM prompt input:", prompt)
    try:
        raw = call_llm(prompt=prompt, system_prompt=SYSTEM_PROMPT, model=DORK_MODEL, temperature=0.4)
        print("[DorkGenerator] Raw LLM response:", raw)

        # Robust JSON extraction
        def robust_extract_json(text):
            # 1. Extract JSON from ```json blocks
            match = re.search(r"```json(.*?)```", text, re.DOTALL)
            if match:
                text = match.group(1)
            # 2. Extract JSON from any code block
            match = re.search(r"```(.*?)```", text, re.DOTALL)
            if match:
                text = match.group(1)
            # 3. Find first {...} block
            match = re.search(r"{[\s\S]*}", text)
            if match:
                text = match.group(0)
            # 4. Try to parse
            try:
                return json.loads(text)
            except Exception:
                pass
            # 5. If it's a list, try to parse as list
            try:
                return json.loads(text.strip())
            except Exception:
                pass
            # 6. Fallback: extract dork-like lines
            dorks = []
            for line in text.splitlines():
                if re.search(r'site:|inurl:|@gmail|info@|contact|whatsapp|shopify', line, re.I):
                    dorks.append(line.strip())
            if dorks:
                return {"keywords": [], "dorks": dorks, "urls": [], "opportunity_score": 70}
            return {"error": "Could not parse JSON or dorks."}

        # Try original parser, then robust fallback
        try:
            result = extract_json_from_response(raw)
        except Exception:
            result = None
        if not result or (isinstance(result, dict) and "error" in result):
            result = robust_extract_json(raw)

        print("[DorkGenerator] Parsed LLM result:", result)

        llm_kws = []
        generated_dorks = []
        if isinstance(result, dict):
            llm_kws = result.get("keywords") or []
            if not llm_kws:
                llm_kws = concrete_keywords
            if not llm_kws:
                llm_kws = ["business"]
            loc = region if region else (country or country_meta["location_terms"][0])
            generated_dorks = generate_dorks_deterministically(llm_kws, country_meta, loc)
        elif isinstance(result, list):
            generated_dorks = result
            llm_kws = concrete_keywords[:5]
        else:
            generated_dorks = []

        print(f"[DorkGenerator] Raw dorks count: {len(generated_dorks)}")

        # ── Permissive cleanup: only strip, dedupe, reject India ──
        clean_dorks = _clean_and_dedupe_dorks(generated_dorks)

        print(f"[DorkGenerator] Dorks after cleanup: {len(clean_dorks)}")

        # ── Fallback safety: if cleanup emptied the list but raw dorks exist, use raw ──
        if not clean_dorks and generated_dorks:
            print("[DorkGenerator] Cleanup removed all dorks — using raw dorks as fallback.")
            clean_dorks = list(dict.fromkeys(d.strip() for d in generated_dorks if d and d.strip()))[:20]

        # Ensure at least some dorks via deterministic fallback
        if len(clean_dorks) < 5:
            print("[DorkGenerator] Too few dorks, augmenting with deterministic fallback.")
            loc = region if region else (country or country_meta["location_terms"][0])
            fallback_dorks = generate_dorks_deterministically(llm_kws, country_meta, loc)
            fallback_clean = _clean_and_dedupe_dorks(fallback_dorks)
            existing = set(d.lower() for d in clean_dorks)
            for d in fallback_clean:
                if d.lower() not in existing:
                    clean_dorks.append(d)
                    existing.add(d.lower())
                if len(clean_dorks) >= 15:
                    break

        print(f"[DorkGenerator] Final dorks count: {len(clean_dorks)}")

        # Generate explanations
        why_this_dork = []
        for d in clean_dorks:
            kw0 = llm_kws[0] if llm_kws else "business"
            reason = f"Advanced B2B lead extraction dork designed to target {kw0} leads in {location} via high-intent filters."
            if "facebook.com" in d:
                reason = f"Extracts direct B2B contacts, phone numbers, and page info for {kw0} in {location} via Facebook."
            elif "linkedin.com" in d:
                reason = f"Targets LinkedIn companies or founders/owners of {kw0} in {location}."
            elif "Shopify" in d or "Powered by Shopify" in d:
                reason = f"Finds Shopify-based ecommerce stores matching {kw0} in {location}."
            elif "@gmail.com" in d:
                reason = f"Directly extracts private and business emails (@gmail) for {kw0} leads in {location}."
            elif "info@" in d:
                reason = f"Finds generic business contact addresses (info@) for {kw0} in {location}."
            elif "contact" in d or "inurl:contact" in d:
                reason = f"Targets direct contact pages of {kw0} websites in {location} to extract forms/details."
            elif "WhatsApp" in d:
                reason = f"Finds direct WhatsApp contact numbers of {kw0} businesses in {location}."
            why_this_dork.append({"dork": d, "reason": reason})

        # Never return empty list silently
        if not clean_dorks:
            print("[DorkGenerator] No dorks after cleanup, using deterministic fallback.")
            loc = region if region else (country or country_meta["location_terms"][0])
            fallback_dorks = generate_dorks_deterministically(concrete_keywords, country_meta, loc)
            clean_dorks = _clean_and_dedupe_dorks(fallback_dorks)
            # Ultimate safety: if still empty, use raw fallback
            if not clean_dorks and fallback_dorks:
                clean_dorks = list(dict.fromkeys(d.strip() for d in fallback_dorks if d and d.strip()))[:20]
            print(f"[DorkGenerator] Final fallback dorks count: {len(clean_dorks)}")

        return {
            "keywords": llm_kws[:5],
            "dorks": clean_dorks[:20],
            "urls": result.get("urls") if isinstance(result, dict) else [],
            "why_this_dork": why_this_dork[:20],
            "opportunity_score": result.get("opportunity_score") if isinstance(result, dict) else 70
        }

    except Exception as e:
        print(f"[DorkGenerator] Exception: {e}")
        print("[DorkGenerator] Falling back to deterministic dork generation.")
        loc = region if region else (country or country_meta["location_terms"][0])
        raw_fallback = generate_dorks_deterministically(concrete_keywords, country_meta, loc)
        clean_dorks = _clean_and_dedupe_dorks(raw_fallback)
        if not clean_dorks and raw_fallback:
            clean_dorks = list(dict.fromkeys(d.strip() for d in raw_fallback if d and d.strip()))[:20]
        why_this_dork = []
        for d in clean_dorks:
            kw0 = concrete_keywords[0] if concrete_keywords else "business"
            reason = f"Advanced B2B lead extraction dork designed to target {kw0} leads in {loc} via high-intent filters."
            why_this_dork.append({"dork": d, "reason": reason})
        print(f"[DorkGenerator] Exception fallback dorks count: {len(clean_dorks)}")
        return {
            "keywords": concrete_keywords[:5],
            "dorks": clean_dorks[:20],
            "urls": [],
            "why_this_dork": why_this_dork[:20],
            "opportunity_score": 70
        }


def _fallback_dorks(keywords: list[str], location: str, sector: str, country: str, region: str) -> dict:
    """Generate advanced fallback dorks using deterministic rules if LLM is unavailable."""
    country_meta = resolve_country_metadata(country, region)
    
    kws = keywords if keywords else SECTOR_TO_KEYWORDS.get(sector.lower(), SECTOR_TO_KEYWORDS.get("b2b services", []))
    if not kws:
        kws = ["services", "business"]
        
    loc = location or country_meta["location_terms"][0]
    
    # Generate advanced templates deterministically
    all_dorks = generate_dorks_deterministically(kws, country_meta, loc)
    clean_dorks = _clean_and_dedupe_dorks(all_dorks)
    # Fallback safety
    if not clean_dorks and all_dorks:
        clean_dorks = list(dict.fromkeys(d.strip() for d in all_dorks if d and d.strip()))[:20]
    
    # Generate explanations
    why_this_dork = []
    for d in clean_dorks:
        kw0 = kws[0] if kws else "business"
        reason = f"Advanced B2B lead extraction dork designed to target {kw0} leads in {loc} via high-intent filters."
        if "facebook.com" in d:
            reason = f"Extracts direct B2B contacts, phone numbers, and page info for {kw0} in {loc} via Facebook."
        elif "linkedin.com" in d:
            reason = f"Targets LinkedIn companies or founders/owners of {kw0} in {loc}."
        elif "Shopify" in d or "Powered by Shopify" in d:
            reason = f"Finds Shopify-based ecommerce stores matching {kw0} in {loc}."
        elif "@gmail.com" in d:
            reason = f"Directly extracts private and business emails (@gmail) for {kw0} leads in {loc}."
        elif "info@" in d:
            reason = f"Finds generic B2B contact addresses (info@) for {kw0} in {loc}."
        elif "contact" in d or "inurl:contact" in d:
            reason = f"Targets direct contact pages of {kw0} websites in {loc} to extract forms/details."
        elif "WhatsApp" in d:
            reason = f"Finds direct WhatsApp contact numbers of {kw0} businesses in {loc}."

        why_this_dork.append({
            "dork": d,
            "reason": reason
        })
        
    return {
        "keywords": kws[:5],
        "dorks": clean_dorks[:20],
        "urls": [],
        "why_this_dork": why_this_dork[:20],
        "opportunity_score": 75,
    }

class DorkGenerator:
    def __init__(self):
        pass

    def generate_from_opportunity(self, opportunity_data: dict, limit: int = 5) -> list[dict]:
        """
        Generate dorks from an opportunity dict.
        Maintains compatibility with the service layer.
        """
        # Convert opportunity_data to a 'trend' dict expected by generate_dorks_for_trend
        trend = {
            "sector": opportunity_data.get("category", ""),
            "country": opportunity_data.get("country", ""),
            "region": opportunity_data.get("region", ""),
            "trend_name": opportunity_data.get("trend_summary", ""),
            "recommended_service": opportunity_data.get("target_service", ""),
            "business_requirements": []
        }
        
        result = generate_dorks_for_trend(trend)
        
        dorks_list = []
        why_list = result.get("why_this_dork", [])
        
        # Build the structured list of dicts expected by service.py
        for i, d in enumerate(result.get("dorks", [])[:limit]):
            reason = "General discovery intent"
            # Try to find reason in why_this_dork
            if isinstance(why_list, list):
                for w in why_list:
                    if isinstance(w, dict) and w.get("dork") == d:
                        reason = w.get("reason", reason)
                        break
                    
            dorks_list.append({
                "dork": d,
                "dork_type": "business_discovery", # Default type
                "intent": reason,
                "score": result.get("opportunity_score", 70)
            })
            
        return dorks_list
        
    def generate_manual(self, config: dict) -> list[dict]:
        """
        Generate dorks manually based on config.
        Maintains compatibility with the service layer's manual generator mode.
        """
        country_meta = resolve_country_metadata(config.get("country", ""), config.get("region", ""))
        keywords = config.get("keywords", [])
        if not keywords and config.get("category"):
            keywords = [config.get("category")]
            
        dorks = generate_dorks_deterministically(
            keywords=keywords,
            country_meta=country_meta,
            location=config.get("region") or config.get("country") or ""
        )
        
        dorks_list = []
        for d in dorks[:config.get("num_dorks", 10)]:
            dorks_list.append({
                "dork": d,
                "dork_type": "manual_discovery",
                "intent": f"Manually generated dork for {config.get('category', 'business')}",
                "quality_score": 75
            })
        return dorks_list
