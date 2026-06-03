import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.database import SessionLocal
from modules.database.models import Campaign, GeneratedDork, ScrapingJob
from modules.dork_optimizer.service import DorkOptimizerService
from modules.jobs.worker import BackgroundWorker
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_audit():
    db = SessionLocal()
    
    # Use existing campaign to avoid foreign key constraints
    campaign = db.query(Campaign).first()
    if not campaign:
        logging.error("No campaigns found in DB.")
        return

    # Create dummy dork
    dork = GeneratedDork(
        dork='site:linkedin.com/in "software engineer" "new york"',
        dork_type="test",
        quality_score=90,
        status="draft"
    )
    db.add(dork)
    db.commit()
    db.refresh(dork)
    
    # Send to scraper
    service = DorkOptimizerService(db)
    result = service.send_dorks_to_scraper([dork.id], campaign.id, platform="serper_bulk")
    logging.info(f"Trigger result: {result}")
    
    db.close()
    
    # Run the scraping planner directly simulating the worker
    db2 = SessionLocal()
    try:
        from sqlalchemy.orm import joinedload
        from modules.jobs.scraping_planner import ScrapingPlanner
        
        job_id = result["job_id"]
        job = db2.query(ScrapingJob).options(
            joinedload(ScrapingJob.campaign)
        ).filter(ScrapingJob.id == job_id).first()
        
        if job:
            camp_name = job.campaign.campaign_name if job.campaign else f"ID:{job.campaign_id[:8]}"
            logging.info(f"Worker picked up pending job: {job.id} (Campaign: {camp_name})")
            logging.info(f"[DIAGNOSTIC] Worker picked up job {job.id} and initializing ScrapingPlanner")
            planner = ScrapingPlanner(db2)
            planner.execute_job(job.id)
    finally:
        db2.close()

if __name__ == "__main__":
    run_audit()
