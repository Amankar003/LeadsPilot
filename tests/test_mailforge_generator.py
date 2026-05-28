from modules.mailforge.generator import MailForgeGenerator

def test_generate_email_fallback():
    # If API keys are not configured, generator will use the robust fallback template
    generator = MailForgeGenerator()
    lead = {
        "business_name": "Sunny Cafe",
        "website": "https://sunnycafe.com",
        "category": "Cafe",
        "location": "Miami"
    }
    campaign_config = {
        "tone": "friendly",
        "email_length": "medium",
        "goal": "book a call",
        "target_service": "website builder"
    }
    
    res = generator.generate_email(lead, campaign_config)
    
    assert "subject" in res
    assert "body" in res
    assert "opening_line" in res
    assert len(res["followups"]) == 3
    assert res["followups"][0]["followup_number"] == 1
