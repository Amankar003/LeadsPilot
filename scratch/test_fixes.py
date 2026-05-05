import sys
import os
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.ai.email_generator import EmailGenerator

def test_email_generation():
    generator = EmailGenerator()
    
    lead_data = {
        "name": "Test Salon",
        "phone": "1234567890",
        "category": "Salon",
        "description": "A very long description that should be truncated by our new normalization logic. " * 10
    }
    
    sender = {
        "sender_name": "Aman",
        "sender_role": "AI Engineer",
        "agency_website": "https://3fitech.com"
    }
    
    print("--- Testing Email Generation ---")
    try:
        # This will call .format() on the prompt. If escaping worked, no KeyError.
        # It might return a quota error if API is still exhausted, which is what we want to test.
        result = generator.generate_draft(lead_data, sender=sender)
        
        print(f"Success! Result keys: {list(result.keys())}")
        print(f"Subject: {result.get('subject')}")
        print(f"Personalization used: {result.get('personalization_used')}")
        
    except KeyError as e:
        print(f"FAILED: KeyError on {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    test_email_generation()
