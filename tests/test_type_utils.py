from utils.type_utils import safe_float, safe_int

def test_safe_float():
    assert safe_float(4.5) == 4.5
    assert safe_float("4.5") == 4.5
    assert safe_float("4.5 stars") == 4.5
    assert safe_float("rating: 4.2") == 4.2
    assert safe_float("N/A") is None
    assert safe_float("None") is None
    assert safe_float("") is None
    assert safe_float(None) is None
    assert safe_float("abc") is None

def test_safe_int():
    assert safe_int(120) == 120
    assert safe_int("120") == 120
    assert safe_int("1,234") == 1234
    assert safe_int("(45)") == 45
    assert safe_int("42.0") == 42
    assert safe_int("45 reviews") == 45
    assert safe_int("N/A") is None
    assert safe_int("None") is None
    assert safe_int("") is None
    assert safe_int(None) is None
    assert safe_int("abc") is None
