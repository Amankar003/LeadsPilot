from modules.database.repositories import LeadRepository
from utils.hash_utils import generate_lead_hash

class Deduplicator:
    def __init__(self, lead_repo: LeadRepository):
        self.lead_repo = lead_repo
        
    def is_duplicate(self, lead_data: dict) -> bool:
        """
        Check if a lead already exists in the database.
        Returns True if duplicate, False otherwise.
        """
        email = lead_data.get('email')
        phone = lead_data.get('phone')
        website = lead_data.get('website')
        
        # Check by email first (strongest indicator)
        if email and self.lead_repo.check_duplicate(email=email):
            return True
            
        # Check by phone
        if phone and self.lead_repo.check_duplicate(phone=phone):
            return True
            
        # Check by website
        if website and self.lead_repo.check_duplicate(website=website):
            return True
            
        # Check by lead hash (business name + location + phone + website)
        lead_hash = generate_lead_hash(
            lead_data.get('business_name'),
            phone,
            website,
            lead_data.get('address') # using address as location
        )
        lead_data['lead_hash'] = lead_hash
        
        if self.lead_repo.check_duplicate(lead_hash=lead_hash):
            return True
            
        return False
