from modules.input.instruction_normalizer import normalize_instruction

def parse_manual_input(campaign_name, platform, category, location, limit, required_fields):
    data = {
        "campaign_name": campaign_name,
        "platform": platform,
        "category": category,
        "location": location,
        "limit": limit,
        "required_fields": required_fields
    }
    return normalize_instruction(data)
