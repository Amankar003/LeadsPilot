def normalize_instruction(data: dict) -> dict:
    """
    Normalizes the input dictionary to ensure required fields and formats.
    """
    return {
        "campaign_name": str(data.get("campaign_name", "")).strip(),
        "platform": str(data.get("platform", "google_maps")).strip().lower(),
        "category": str(data.get("category", "")).strip(),
        "location": str(data.get("location", "")).strip(),
        "limit": int(data.get("limit", 100)),
        "required_fields": data.get("required_fields", [])
    }
