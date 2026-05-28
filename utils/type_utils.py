import re

def safe_float(val) -> float | None:
    """
    Safely converts a value to float.
    Handles None, empty values, 'N/A', strings with suffixes like '4.5 stars', etc.
    Returns None if missing, invalid, or empty.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
        
    s = str(val).strip()
    if not s or s.lower() in ("n/a", "none", "null", "undefined", ""):
        return None
        
    # Extract decimal or integer sequence
    match = re.search(r"[-+]?\d*\.\d+|\d+", s)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            pass
            
    return None

def safe_int(val) -> int | None:
    """
    Safely converts a value to integer.
    Handles None, empty values, commas like '1,234', decimals like '42.0',
    parentheses like '(45)', and string suffixes.
    Returns None if missing, invalid, or empty.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
        
    s = str(val).strip()
    if not s or s.lower() in ("n/a", "none", "null", "undefined", ""):
        return None
        
    # Remove commas, e.g. "1,250" -> "1250"
    s = s.replace(",", "")
    
    # Extract first sequence of digits
    match = re.search(r"[-+]?\d+", s)
    if match:
        try:
            return int(match.group(0))
        except ValueError:
            pass
            
    # Try parsing as float first and then converting to integer
    f_val = safe_float(val)
    if f_val is not None:
        return int(f_val)
        
    return None
