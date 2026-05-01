from sqlalchemy.orm import Session
from modules.database.repositories import JobRepository, LeadRepository
from modules.scraping.scraper_factory import get_scraper
from modules.scraping.website_scraper import WebsiteScraper
from modules.cleaning.deduplicator import Deduplicator
from utils.constants import JOB_RUNNING, JOB_COMPLETED, JOB_FAILED, LEAD_CLEANED, LEAD_STORED
import datetime
from utils.logging_utils import get_logger

logger = get_logger(__name__)

class ScrapingPlanner:
    def __init__(self, db: Session):
        self.db = db
        self.job_repo = JobRepository(db)
        self.lead_repo = LeadRepository(db)
        self.deduplicator = Deduplicator(self.lead_repo)
        self.website_scraper = WebsiteScraper()
        
    def execute_job(self, job_id: str):
        """
        Executes a scraping job.
        """
        job = self.job_repo.update_status(job_id, JOB_RUNNING, started_at=datetime.datetime.utcnow())
        if not job:
            logger.error(f"Job {job_id} not found.")
            return
            
        try:
            scraper = get_scraper(job.platform)
            leads = scraper.scrape(query=job.category, limit=job.limit, location=job.location)
            
            job.total_scraped = len(leads)
            self.db.commit()
            
            for lead_data in leads:
                # Website scraping for emails
                if lead_data.get('website'):
                    emails = self.website_scraper.extract_emails_from_url(lead_data['website'])
                    if emails:
                        lead_data['email'] = emails[0]
                        lead_data['has_email'] = True
                        lead_data['raw_data']['all_emails'] = emails
                        
                # Update flags
                if lead_data.get('phone'):
                    lead_data['has_phone'] = True
                if lead_data.get('website'):
                    lead_data['has_website'] = True
                    
                # Deduplication check
                if self.deduplicator.is_duplicate(lead_data):
                    job.total_duplicates += 1
                    self.db.commit()
                    continue
                    
                # Save lead
                try:
                    self.lead_repo.create(
                        campaign_id=job.campaign_id,
                        scraping_job_id=job.id,
                        business_name=lead_data['business_name'],
                        category=lead_data['category'],
                        phone=lead_data['phone'],
                        email=lead_data['email'],
                        website=lead_data['website'],
                        address=lead_data['address'],
                        rating=lead_data['rating'],
                        reviews_count=lead_data['reviews_count'],
                        source=lead_data['source'],
                        google_maps_url=lead_data['google_maps_url'],
                        has_email=lead_data.get('has_email', False),
                        has_phone=lead_data.get('has_phone', False),
                        has_website=lead_data.get('has_website', False),
                        lead_hash=lead_data['lead_hash'],
                        status=LEAD_STORED,
                        raw_data=lead_data['raw_data']
                    )
                    job.total_saved += 1
                except Exception as e:
                    job.total_failed += 1
                    logger.error(f"Failed to save lead: {str(e)}")
                    self.db.rollback()
                    
                self.db.commit()
                
            self.job_repo.update_status(job_id, JOB_COMPLETED, completed_at=datetime.datetime.utcnow())
            
        except Exception as e:
            logger.error(f"Job {job_id} failed: {str(e)}")
            self.job_repo.update_status(job_id, JOB_FAILED, error_message=str(e), completed_at=datetime.datetime.utcnow())
