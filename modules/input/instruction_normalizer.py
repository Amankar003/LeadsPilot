def normalize_instruction(data: dict) -> dict:
    """
    Normalizes the input dictionary to ensure required fields and formats.
    """
    # Normalize category: allow comma-separated or newline-separated multiple queries
    raw_category = str(data.get("category", "")).strip()
    if "," in raw_category:
        import re
        queries = [q.strip() for q in re.split(r"[,\n]+", raw_category) if q.strip()]
        category = "\n".join(queries)
    else:
        category = raw_category

    return {
        "campaign_name": str(data.get("campaign_name", "")).strip(),
        "platform": str(data.get("platform", "google_maps")).strip().lower(),
        "category": category,
        "location": str(data.get("location", "")).strip(),
        "limit": int(data.get("limit")) if data.get("limit") and int(data.get("limit")) > 0 else None,
        "required_fields": data.get("required_fields", []),
        "enable_fallback": bool(data.get("enable_fallback", True)),
        "max_fallback_results": int(data.get("max_fallback_results", 5)),
        "max_fallback_pages": int(data.get("max_fallback_pages", 2))
    }
