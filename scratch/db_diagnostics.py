import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.database import SessionLocal
from modules.database.models import Lead, Campaign
from sqlalchemy import func

def run_diagnostics():
    db = SessionLocal()
    try:
        # Total leads
        total_leads = db.query(Lead).count()
        print(f"Total Leads: {total_leads}")
        
        # Campaign-wise
        print("\nCampaign-wise Counts:")
        c_counts = db.query(Lead.campaign_id, func.count(Lead.id)).group_by(Lead.campaign_id).all()
        for c_id, count in c_counts:
            camp = db.query(Campaign).filter(Campaign.id == c_id).first()
            c_name = camp.campaign_name if camp else c_id
            print(f"  {c_name}: {count} leads")
            
        # Duplicate by Name
        print("\nDuplicate By Name:")
        dup_names = db.query(Lead.business_name, func.count(Lead.id)).filter(Lead.business_name != None, Lead.business_name != '').group_by(Lead.business_name).having(func.count(Lead.id) > 1).order_by(func.count(Lead.id).desc()).limit(10).all()
        for name, count in dup_names:
            print(f"  {name}: {count}")

        # Duplicate by Website
        print("\nDuplicate By Website:")
        dup_web = db.query(Lead.website, func.count(Lead.id)).filter(Lead.website != None, Lead.website != '').group_by(Lead.website).having(func.count(Lead.id) > 1).order_by(func.count(Lead.id).desc()).limit(10).all()
        for web, count in dup_web:
            print(f"  {web}: {count}")

        # Duplicate by Phone
        print("\nDuplicate By Phone:")
        dup_phone = db.query(Lead.phone, func.count(Lead.id)).filter(Lead.phone != None, Lead.phone != '').group_by(Lead.phone).having(func.count(Lead.id) > 1).order_by(func.count(Lead.id).desc()).limit(10).all()
        for p, count in dup_phone:
            print(f"  {p}: {count}")
            
    finally:
        db.close()

if __name__ == "__main__":
    run_diagnostics()
