from sqlalchemy.orm import Session
from modules.database.repositories import JobRepository, LeadRepository
from modules.scraping.scraper_factory import get_scraper
from modules.scraping.google_email_scraper import GoogleEmailScraper
from modules.scraping.website_scraper import WebsiteScraper
from modules.cleaning.deduplicator import Deduplicator
from utils.constants import JOB_RUNNING, JOB_COMPLETED, JOB_FAILED, JOB_STOPPED, LEAD_CLEANED, LEAD_STORED
import datetime
from utils.logging_utils import get_logger

logger = get_logger(__name__)

def is_fake_business_name(name, query=""):
    if not name:
        return True

    name_lower = name.lower().strip()
    query_lower = query.lower().strip()

    fake_keywords = [
        "phone lead",
        "email lead",
        "search result",
        "google search",
        "site:facebook.com",
        "site:instagram.com",
        "site:linkedin.com"
    ]

    if any(keyword in name_lower for keyword in fake_keywords):
        return True

    if query_lower and query_lower in name_lower:
        return True

    return False

def is_invalid_source_url(url):
    if not url:
        return True

    url = url.lower()

    invalid_patterns = [
        "google.com/search",
        "bing.com/search",
        "duckduckgo.com",
        "search?q="
    ]

    return any(pattern in url for pattern in invalid_patterns)

class ScrapingPlanner:
    def __init__(self, db: Session):
        self.db = db
        self.job_repo = JobRepository(db)
        self.lead_repo = LeadRepository(db)
        self.deduplicator = Deduplicator(self.lead_repo)
        self.website_scraper = WebsiteScraper()
        
    def execute_job(self, job_id: str):
        """
        Executes a scraping job with fallback mechanism.
        """
        from utils.constants import PLATFORM_GOOGLE_SERP, PLATFORM_GOOGLE_MAPS
        
        job = self.job_repo.update_status(job_id, JOB_RUNNING, started_at=datetime.datetime.utcnow())
        if not job:
            logger.error(f"Job {job_id} not found.")
            return
            
        try:
            queries = [q.strip() for q in job.category.split('\n') if q.strip()]
            
            for query in queries:
                # Check for stop signal
                self.db.refresh(job)
                if job.status == JOB_STOPPED:
                    logger.info(f"Job {job_id} stopped by user.")
                    break
                
                def should_stop():
                    self.db.refresh(job)
                    return job.status == JOB_STOPPED

                logger.info(f"Starting scrape for query: {query} using platform: {job.platform}")
                
                leads_found_before = job.total_saved
                
                # Primary scraper
                try:
                    from utils.constants import PLATFORM_SERPER_BULK
                    if job.platform == PLATFORM_SERPER_BULK:
                        from modules.scraping.bulk_serper_runner import run_bulk_serper_scraping
                        # Bulk runner handles its own internal loop and website scraping
                        run_bulk_serper_scraping(
                            db=self.db,
                            campaign_id=job.campaign_id,
                            job_id=job.id,
                            main_query=query,
                            location=job.location,
                            target_count=10000,
                            scrape_websites=True
                        )
                        # Mark as processed so it doesn't try fallback
                        leads_count = 1 
                    else:
                        scraper = get_scraper(job.platform)
                        leads_count = 0
                        results = self._process_leads(job, scraper, query, should_stop)
                        if results is None:
                            logger.warning(f"Scraper for {job.platform} returned None, using empty list.")
                            results = []
                        
                        for lead_data in results:
                            leads_count += 1
                    
                    logger.info(f"Query '{query}': Scraping completed for {job.platform}")
                    
                except Exception as e:
                    logger.error(f"Error with {job.platform} scraper: {e}")
                    leads_count = 0
                
                # Fallback to Google Maps if SERP didn't produce results
                if (job.enable_fallback and 
                    job.platform == PLATFORM_GOOGLE_SERP and 
                    leads_count == 0 and 
                    job.status != JOB_STOPPED):
                    
                    logger.warning(f"No leads found with SERP. Trying fallback with Google Maps...")
                    try:
                        fallback_scraper = GoogleMapsScraper()
                        fallback_limit = job.max_fallback_results if job.max_fallback_results else job.limit
                        
                        for lead_data in self._process_leads(job, fallback_scraper, query, should_stop, fallback_limit):
                            pass
                        
                        logger.info(f"Fallback completed for query: {query}")
                    except Exception as e:
                        logger.error(f"Fallback Google Maps scraper failed: {e}")
                    finally:
                        fallback_scraper.close()
                
                if job.status == JOB_STOPPED: 
                    break

            if job.status != JOB_STOPPED:
                self.job_repo.update_status(job_id, JOB_COMPLETED, completed_at=datetime.datetime.utcnow())
            
        except Exception as e:
            logger.error(f"Error executing job {job_id}: {e}")
            self.job_repo.update_status(job_id, JOB_FAILED)
            self.db.commit()

    def _process_leads(self, job, scraper, query, should_stop, limit=None):
        """
        Process leads from scraper and save them to database.
        """
        if limit is None:
            limit = job.limit
            
        scraped_results = scraper.scrape(query=query, limit=limit, location=job.location, should_stop=should_stop)
        if scraped_results is None:
            logger.warning(f"Scraper returned None for query: {query}")
            return
            
        for lead_data in scraped_results:
            # Check for stop signal again during processing
            self.db.refresh(job)
            if job.status == JOB_STOPPED: 
                break

            business_name = lead_data.get("business_name", "")
            source_url = lead_data.get("google_maps_url", "")
            if not source_url:
                source_url = lead_data.get("raw_data", {}).get("source_url", "")

            # VALIDATION LOGIC:
            # 1. Ensure the business name is a real name, not a placeholder (e.g., 'Phone Lead', 'Email Lead')
            #    or just the raw search query. Empty names or placeholder names are skipped.
            if is_fake_business_name(business_name, query):
                logger.info(f"Skipping lead due to fake business name: {business_name}")
                continue

            # 2. Ensure the source URL is an actual business page or profile, not a Google search result URL.
            #    We don't want to save search engine URLs as the business website or source.
            if is_invalid_source_url(source_url):
                logger.info(f"Skipping lead due to invalid source URL: {source_url}")
                continue

            # Website scraping for emails
            email_source = "website"
            email_confidence = "medium"
            
            if lead_data.get('website'):
                emails = self.website_scraper.extract_emails_from_url(lead_data['website'])
                if emails:
                    lead_data['email'] = emails[0]
                    lead_data['has_email'] = True
                    lead_data['raw_data']['all_emails'] = emails
                    logger.info(f"Website email found for {lead_data['business_name']}")
            
            lead_data['email_source'] = email_source if lead_data.get('email') else None
            lead_data['email_confidence'] = email_confidence if lead_data.get('email') else None
                    
            # Update flags
            if lead_data.get('phone'):
                lead_data['has_phone'] = True
            if lead_data.get('website'):
                lead_data['has_website'] = True
                
            job.total_scraped += 1

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
                    category=query,
                    phone=lead_data.get('phone'),
                    email=lead_data.get('email'),
                    website=lead_data.get('website'),
                    address=lead_data.get('address'),
                    has_email=lead_data.get('has_email', False),
                    has_phone=lead_data.get('has_phone', False),
                    has_website=lead_data.get('has_website', False),
                    email_source=lead_data.get('email_source'),
                    email_confidence=lead_data.get('email_confidence'),
                    lead_hash=lead_data.get('lead_hash'),
                    source=lead_data.get('source'),
                    google_maps_url=lead_data.get('google_maps_url'),
                    rating=lead_data.get('rating'),
                    reviews_count=lead_data.get('reviews_count'),
                    raw_data=lead_data.get('raw_data', {})
                )
                job.total_saved += 1
            except Exception as e:
                logger.error(f"Error saving lead: {e}")
                self.db.rollback()

            self.db.commit()
            yield lead_data
