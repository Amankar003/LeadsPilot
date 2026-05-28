import os
import shutil
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config.database import SessionLocal
from backend.services.email_enrichment_service import (
    parse_uploaded_email_file,
    detect_email_column,
    enrich_email_lead,
    save_enriched_lead
)
from modules.database.models import Campaign, ScrapingJob

app = FastAPI(title="LeadPilot Backend API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/leads/upload-email-list")
async def upload_email_list(
    campaign_id: str = Form(...),
    file: UploadFile = File(...),
    campaign_name: str = Form(None),
    category: str = Form(None),
    location: str = Form(None)
):
    """
    Exposes POST /api/leads/upload-email-list.
    Accepts campaign_id and a CSV/XLSX file stream, performing real-time business enrichment.
    """
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, file.filename)
    
    try:
        # Save upload to temporary file path
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Parse emails DataFrame
        df = parse_uploaded_email_file(temp_path)
        email_col = detect_email_column(df)
        
        db = SessionLocal()
        try:
            # Resolve campaign (fetch existing or create dynamically)
            if campaign_id.upper() == "NEW":
                if not campaign_name:
                    raise HTTPException(status_code=400, detail="campaign_name is required when creating a new campaign")
                
                from modules.database.models import get_or_create_default_user
                user = get_or_create_default_user(db)
                from modules.database.repositories import CampaignRepository
                campaign = CampaignRepository(db).create(
                    user_id=user.id,
                    campaign_name=campaign_name,
                    category=category or "General Business",
                    location=location or "Unknown",
                    platform="email_only_enrichment_api",
                    status="COMPLETED"
                )
                campaign_id = campaign.id
            else:
                campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
                if not campaign:
                    raise HTTPException(status_code=404, detail="Campaign not found")
                
            # Create completed ScrapingJob for tracking
            job = ScrapingJob(
                campaign_id=campaign_id,
                platform="email_only_enrichment_api",
                category=campaign.category,
                location=campaign.location,
                status="RUNNING",
                total_scraped=len(df),
                total_saved=0
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            
            saved_count = 0
            updated_count = 0
            results = []
            
            for _, row_series in df.iterrows():
                row_dict = row_series.to_dict()
                # Ensure the detected email column is mapped to 'email' key in dict
                if email_col in row_dict:
                    row_dict["email"] = row_dict[email_col]
                    
                # Run lead enrichment
                enriched = enrich_email_lead(row_dict, campaign_id=campaign_id, db=db)
                
                # Save enriched leads to DB
                if enriched["enrichment_status"] not in ["INVALID_EMAIL", "FREE_EMAIL_NO_BUSINESS_NAME"]:
                    lead_obj, action = save_enriched_lead(enriched, campaign_id, job.id, db)
                    if action == "created":
                        saved_count += 1
                    else:
                        updated_count += 1
                        
                results.append(enriched)
                
            # Update ScrapingJob stats
            job.status = "COMPLETED"
            job.total_saved = saved_count
            db.commit()
            
            return {
                "campaign_id": campaign_id,
                "job_id": job.id,
                "total_rows": len(df),
                "saved_count": saved_count,
                "updated_count": updated_count,
                "results": results
            }
            
        finally:
            db.close()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8506, reload=True)
