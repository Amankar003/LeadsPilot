import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from modules.scraping.google_maps_scraper import GoogleMapsScraper
from modules.input.instruction_normalizer import normalize_instruction

def test_normalization():
    print("Testing normalization...")
    
    # Test with limit
    data1 = {"category": "salons", "limit": 10}
    norm1 = normalize_instruction(data1)
    print(f"Limit 10 -> {norm1['limit']}")
    assert norm1['limit'] == 10
    
    # Test with limit 0 (Scrape All)
    data2 = {"category": "salons", "limit": 0}
    norm2 = normalize_instruction(data2)
    print(f"Limit 0 -> {norm2['limit']}")
    assert norm2['limit'] is None
    
    # Test with missing limit
    data3 = {"category": "salons"}
    norm3 = normalize_instruction(data3)
    print(f"Missing limit -> {norm3['limit']}")
    assert norm3['limit'] is None

def test_scraper_instantiation():
    print("Testing scraper instantiation...")
    scraper = GoogleMapsScraper()
    print("Scraper instantiated successfully.")

if __name__ == "__main__":
    try:
        test_normalization()
        test_scraper_instantiation()
        print("\n✅ Verification successful!")
    except Exception as e:
        print(f"\n❌ Verification failed: {str(e)}")
        sys.exit(1)
