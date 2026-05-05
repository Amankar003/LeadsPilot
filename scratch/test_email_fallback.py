import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from modules.scraping.google_email_scraper import GoogleEmailScraper

def test_fallback():
    print("Testing GoogleEmailScraper fallback...")
    scraper = GoogleEmailScraper(max_pages=1, headless=True)
    
    try:
        results = scraper.find_emails_for_lead(
            business_name="Looks Salon",
            location="Noida",
            website="http://www.lookssalon.in/",
            max_emails=2
        )
        
        print(f"\nFound {len(results)} fallback emails:")
        for res in results:
            print(f" - {res['email']} (Confidence: {res['confidence']}, Source: {res['source_url'][:50]}...)")
        
        if results:
            print("\n✅ Fallback test successful!")
        else:
            print("\n⚠️ No emails found, but search completed.")
            
    except Exception as e:
        print(f"\n❌ Fallback test failed: {str(e)}")
    finally:
        scraper.close()

if __name__ == "__main__":
    test_fallback()
