import re

def build_final_query(query: str, location: str = "") -> str:
    query = (query or "").strip()
    location = (location or "").strip()

    if not location:
        return query

    if location.lower() in query.lower():
        return query

    return f"{query} in {location}"

def generate_query_variations(main_query: str, location: str = "", limit: int = 50) -> list[str]:
    """
    Generates many useful search query variations for local business lead generation.
    """
    if not main_query:
        return []

    variations = []
    
    # Clean inputs
    main_query = main_query.strip()
    location = location.strip() if location else ""
    
    # 1. Base Templates
    templates = [
        "{query}",
        "best {query}",
        "top {query}",
        "affordable {query}",
        "premium {query}",
        "certified {query}",
        "professional {query}",
        "top-rated {query}",
        "local {query}",
        "{query} near me",
        "{query} services",
        "{query} solutions",
        "{query} agency",
        "{query} firm",
        "{query} experts",
        "{query} specialists",
        "{query} consultants",
        "{query} contractors",
        "{query} companies",
        "{query} providers",
        "{query} corporate",
        "{query} commercial",
        "{query} residential",
        "{query} b2b",
        "{query} enterprise",
        "{query} contact number",
        "{query} official website",
        "{query} email address",
        "{query} list",
        "list of {query}",
        "{query} directory",
        "{query} business",
        "{query} reviews",
        "hire {query}",
        "find {query}"
    ]

    # Start building
    for t in templates:
        q = t.format(query=main_query)
        variations.append(build_final_query(q, location))

    # 2. Local Modifiers
    local_modifiers = [
        "downtown", "north", "south", "east", "west", "central",
        "business district", "commercial area", "industrial area",
        "city center", "metro area", "suburbs", "county",
        "regional", "near main market", "near metro station",
        "near airport", "near highway", "local area",
        "Sector 1", "Sector 2", "Sector 3", "Sector 4", "Sector 5",
        "Phase 1", "Phase 2", "Phase 3"
    ]
    
    for loc_mod in local_modifiers:
        q = f"{main_query} {loc_mod}"
        variations.append(build_final_query(q, location))

    # Deduplicate and clean
    seen = set()
    unique_variations = []
    for v in variations:
        v_clean = re.sub(r'\s+', ' ', v).strip()
        if v_clean and v_clean.lower() not in seen:
            seen.add(v_clean.lower())
            unique_variations.append(v_clean)

    return unique_variations[:limit]
