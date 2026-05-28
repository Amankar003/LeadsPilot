import pandas as pd
from sqlalchemy.orm import Session
from modules.database.models import Campaign, Lead
from utils.hash_utils import generate_lead_hash
from utils.type_utils import safe_float, safe_int
import uuid
from datetime import datetime

def import_dataframe_to_leads(db: Session, df: pd.DataFrame, campaign_name: str):
    # 1. Create or get campaign
    campaign = db.query(Campaign).filter(Campaign.campaign_name == campaign_name).first()
    if not campaign:
        campaign = Campaign(
            id=f"camp_{uuid.uuid4().hex[:8]}",
            campaign_name=campaign_name,
            platform="direct_import",
            category="Imported",
            location="Unknown",
            limit=len(df),
            status="COMPLETED"
        )
        db.add(campaign)
        db.commit()

    # Define standard column mappings
    # Mapping common variations to standard fields
    def get_col_val(row, possible_names):
        for name in possible_names:
            if name in row and pd.notna(row[name]):
                return str(row[name]).strip()
        return None

    added = 0
    duplicates = 0

    for _, row in df.iterrows():
        # Standardize field extraction
        business_name = get_col_val(row, ['name', 'Business Name', 'Business', 'Company', 'business_name', 'Title'])
        email = get_col_val(row, ['email', 'Email', 'Email Address', 'contact_email'])
        phone = get_col_val(row, ['phone', 'Phone', 'Phone Number', 'contact_phone', 'mobile'])
        website = get_col_val(row, ['website', 'Website', 'URL', 'url', 'site'])
        location = get_col_val(row, ['address', 'Address', 'Location', 'location', 'city'])
        
        # If no business name is provided, default to a generic name
        if not business_name:
            if email:
                business_name = email.split('@')[0]
            elif website:
                business_name = website.replace('https://', '').replace('http://', '').split('/')[0]
            else:
                business_name = "Unknown Business"

        # Generate lead hash for duplicate checking
        lead_hash = generate_lead_hash(
            business_name=business_name,
            website=website,
            location=location,
            domain=website.replace('https://', '').replace('http://', '').split('/')[0] if website else None
        )

        # Check for existing duplicate
        existing_lead = db.query(Lead).filter(Lead.lead_hash == lead_hash).first()
        if existing_lead:
            duplicates += 1
            continue

        # Save the full row as raw_data
        raw_data = row.to_dict()
        
        # Ensure raw_data is clean JSON serializable
        clean_raw_data = {}
        for k, v in raw_data.items():
            if pd.isna(v):
                clean_raw_data[str(k)] = None
            else:
                clean_raw_data[str(k)] = str(v)

        lead = Lead(
            campaign_id=campaign.id,
            scraping_job_id=None,  # Direct import, no job
            business_name=business_name,
            category="Imported",
            phone=phone,
            email=email,
            website=website,
            address=location,
            has_email=bool(email),
            has_phone=bool(phone),
            has_website=bool(website),
            source="direct_import",
            lead_hash=lead_hash,
            raw_data=clean_raw_data,
            status="STORED",
            created_at=datetime.utcnow()
        )
        db.add(lead)
        added += 1

    db.commit()
    return added, duplicates
