import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.database import SessionLocal
from modules.database.models import Lead
from modules.database.repositories import LeadRepository

def check_leads():
    db = SessionLocal()
    try:
        leads_direct = db.query(Lead).all()
        print(f"Direct DB count: {len(leads_direct)}")
        if leads_direct:
            print(f"First Lead Campaign ID: {leads_direct[-1].campaign_id}")
            print(f"First Lead Title: {leads_direct[-1].business_name}")
            print(f"First Lead Status: {leads_direct[-1].status}")
            print(f"First Lead User ID: {leads_direct[-1].user_id}")
        
        repo_leads = LeadRepository(db).get_all()
        print(f"Repository count: {len(repo_leads)}")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_leads()
