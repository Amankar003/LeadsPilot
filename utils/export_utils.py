import pandas as pd
import os
from config.settings import EXPORTS_DIR
from datetime import datetime

def export_leads_to_csv(leads, filename=None):
    if not leads:
        return None
        
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"leads_export_{timestamp}.csv"
        
    filepath = os.path.join(EXPORTS_DIR, filename)
    
    # Convert leads objects to dictionaries
    leads_data = []
    for lead in leads:
        lead_dict = {
            "business_name": lead.business_name,
            "category": lead.category,
            "phone": lead.phone,
            "email": lead.email,
            "website": lead.website,
            "address": lead.address,
            "city": lead.city,
            "state": lead.state,
            "country": lead.country,
            "rating": lead.rating,
            "reviews_count": lead.reviews_count,
            "source": lead.source,
            "status": lead.status,
            "campaign_id": lead.campaign_id
        }
        leads_data.append(lead_dict)
        
    df = pd.DataFrame(leads_data)
    df.to_csv(filepath, index=False)
    
    return filepath
