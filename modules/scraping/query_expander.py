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
        "{query} near me",
        "{query} services",
        "{query} companies",
        "{query} contact number",
        "{query} official website",
        "{query} email address",
        "{query} list",
        "list of {query}",
        "{query} business"
    ]

    # Start building
    for t in templates:
        q = t.format(query=main_query)
        variations.append(build_final_query(q, location))

    # 2. Local Modifiers
    local_modifiers = [
        "near Sector 18", "near Sector 62", "near Sector 63", "near Sector 15",
        "near City Centre", "near main market", "near metro station"
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
