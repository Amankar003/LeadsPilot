from modules.mailforge.enrichment import MailForgeEnricher
from modules.mailforge.constants import ENRICH_STATUS_NEEDS_REVIEW, ENRICH_STATUS_ENRICHED

def test_enrich_invalid_email():
    enricher = MailForgeEnricher()
    res = enricher.enrich_email("not-an-email")
    assert res["enrichment_status"] == "failed"
    assert "Invalid email" in res["notes"]

def test_enrich_free_domain():
    enricher = MailForgeEnricher()
    res = enricher.enrich_email("user@gmail.com")
    assert res["domain"] == "gmail.com"
    assert res["enrichment_status"] == ENRICH_STATUS_NEEDS_REVIEW
    assert "Free email domain" in res["notes"]
    assert res["confidence_score"] == 0.3

def test_enrich_business_domain_fallback():
    # Mock requests.get to raise connection error so it exercises the fallback pathway safely
    def mock_get(*args, **kwargs):
        raise ConnectionError("Mocked Connection Error")
    
    import requests
    original_get = requests.get
    requests.get = mock_get

    try:
        enricher = MailForgeEnricher()
        res = enricher.enrich_email("contact@mybusiness.com")
        assert res["domain"] == "mybusiness.com"
        assert res["website"] == "https://mybusiness.com"
        assert res["business_name"] == "Mybusiness"
        assert res["enrichment_status"] == "partial"
    finally:
        requests.get = original_get

