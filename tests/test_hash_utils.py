from utils.hash_utils import generate_lead_hash, normalize_email, normalize_website, extract_domain

def test_normalize_email():
    assert normalize_email(" TEST@domain.COM  ") == "test@domain.com"
    assert normalize_email("") == ""
    assert normalize_email(None) == ""

def test_normalize_website():
    assert normalize_website("  google.com ") == "https://google.com"
    assert normalize_website("http://apple.com") == "http://apple.com"
    assert normalize_website("") == ""

def test_extract_domain():
    assert extract_domain("user@mycompany.co.uk") == "mycompany.co.uk"
    assert extract_domain("https://www.example.com/some/path?query=1") == "example.com"
    assert extract_domain("") == ""

def test_generate_lead_hash_determinism():
    hash1 = generate_lead_hash(business_name="Acme Corp", email="contact@acme.com")
    hash2 = generate_lead_hash(business_name="Acme Corp", email="contact@acme.com")
    assert hash1 == hash2
    assert len(hash1) == 32 # MD5 output length

def test_generate_lead_hash_priority():
    # Email priority
    hash_with_email = generate_lead_hash(business_name="Test Inc", email="test@test.com", phone="12345")
    hash_with_email_only = generate_lead_hash(email="test@test.com")
    assert hash_with_email == hash_with_email_only

    # Phone priority over business name
    hash_with_phone = generate_lead_hash(business_name="Test Inc", phone="12345")
    hash_with_phone_only = generate_lead_hash(phone="12345")
    assert hash_with_phone == hash_with_phone_only

def test_generate_lead_hash_empty_raises_value_error():
    try:
        generate_lead_hash()
        assert False, "Should raise ValueError"
    except ValueError:
        pass

