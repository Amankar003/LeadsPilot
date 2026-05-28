from sqlalchemy.orm import Session
from modules.database.repositories import JobRepository, LeadRepository
from modules.scraping.scraper_factory import get_scraper
from modules.scraping.google_email_scraper import GoogleEmailScraper
from modules.scraping.google_maps_scraper import GoogleMapsScraper
from modules.scraping.website_scraper import WebsiteScraper
from modules.cleaning.deduplicator import Deduplicator
from utils.constants import JOB_RUNNING, JOB_COMPLETED, JOB_FAILED, JOB_STOPPED, LEAD_CLEANED, LEAD_STORED
import datetime
from utils.logging_utils import get_logger
from utils.type_utils import safe_float, safe_int
from config.database import SessionLocal
from modules.database.models import ScrapingJob

logger = get_logger(__name__)

def update_job_stats(job_id, scraped_delta=0, saved_delta=0, duplicate_delta=0, failed_delta=0, loaded_delta=0, skipped_delta=0, loaded_count=None, status=None):
    """Safely update job statistics using a fresh short-lived session."""
    db = SessionLocal()
    try:
        job = db.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
        if not job:
            return None
        if scraped_delta: job.total_scraped += scraped_delta
        if saved_delta: job.total_saved += saved_delta
        if duplicate_delta: job.total_duplicates += duplicate_delta
        if failed_delta: job.total_failed += failed_delta
        if loaded_delta: job.total_loaded += loaded_delta
        if skipped_delta: job.total_skipped += skipped_delta
        if loaded_count is not None: job.total_loaded = loaded_count
        if status: job.status = status
        db.commit()
        return job
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update job stats for {job_id}: {e}")
    finally:
        db.close()

def is_fake_business_name(name, query=""):
    """
    Detect placeholder or garbage business names.
    NOTE: We do NOT reject names just because they contain the search category.
    E.g. searching 'Hotels' should NOT skip 'The Grand Hotel'.
    Only reject if the name is EXACTLY the query or is a known placeholder.
    """
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

    # Only reject if the business name is EXACTLY the raw search query
    # (not just containing it — real businesses often contain their category)
    if query_lower and name_lower == query_lower:
        return True

    return False

def is_invalid_source_url(url):
    """
    Reject search engine result URLs but allow Google Maps place URLs
    and empty URLs (Google Maps leads may only have a maps URL).
    """
    if not url:
        # Allow empty source URLs — Google Maps leads legitimately may not have one
        return False

    url = url.lower()

    # Allow Google Maps place URLs explicitly
    if "google.com/maps" in url:
        return False

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
            # Extract basic primitives so we don't pass the ORM object across long-running tasks
            job_category = job.category
            job_platform = job.platform
            job_location = job.location
            job_campaign_id = job.campaign_id
            job_limit = job.limit
            job_enable_fallback = job.enable_fallback
            job_max_fallback_results = job.max_fallback_results
            
            queries = [q.strip() for q in job_category.split('\n') if q.strip()]
            
            for query in queries:
                def should_stop():
                    db = SessionLocal()
                    try:
                        j = db.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
                        return j.status == JOB_STOPPED if j else False
                    finally:
                        db.close()

                if should_stop():
                    logger.info(f"Job {job_id} stopped by user.")
                    break

                logger.info(f"Starting scrape for query: {query} using platform: {job_platform}")
                
                # Primary scraper
                try:
                    from utils.constants import PLATFORM_SERPER_BULK
                    if job_platform == PLATFORM_SERPER_BULK:
                        from modules.scraping.bulk_serper_runner import run_bulk_serper_scraping
                        run_bulk_serper_scraping(
                            db=self.db,
                            campaign_id=job_campaign_id,
                            job_id=job_id,
                            main_query=query,
                            location=job_location,
                            target_count=10000,
                            scrape_websites=True
                        )
                        leads_count = 1 
                    else:
                        scraper = get_scraper(job_platform)
                        leads_count = 0
                        results = self._process_leads(job_id, job_campaign_id, job_location, job_limit, scraper, query, should_stop)
                        if results is None:
                            logger.warning(f"Scraper for {job_platform} returned None, using empty list.")
                            results = []
                        
                        for lead_data in results:
                            leads_count += 1
                    
                    logger.info(f"Query '{query}': Scraping completed for {job_platform}")
                    
                except Exception as e:
                    logger.error(f"Error with {job_platform} scraper: {e}")
                    leads_count = 0
                
                # Fallback to Google Maps if SERP didn't produce results
                if (job_enable_fallback and 
                    job_platform == PLATFORM_GOOGLE_SERP and 
                    leads_count == 0 and 
                    not should_stop()):
                    
                    logger.warning(f"No leads found with SERP. Trying fallback with Google Maps...")
                    try:
                        fallback_scraper = GoogleMapsScraper()
                        fallback_limit = job_max_fallback_results if job_max_fallback_results else job_limit
                        
                        for lead_data in self._process_leads(job_id, job_campaign_id, job_location, fallback_limit, fallback_scraper, query, should_stop):
                            pass
                        
                        logger.info(f"Fallback completed for query: {query}")
                    except Exception as e:
                        logger.error(f"Fallback Google Maps scraper failed: {e}")
                    finally:
                        fallback_scraper.close()
                
                if should_stop(): 
                    break

            if not should_stop():
                update_job_stats(job_id, status=JOB_COMPLETED)
            
            # Normalize counts
            db_norm = SessionLocal()
            try:
                j_norm = db_norm.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
                if j_norm:
                    if not should_stop():
                        j_norm.completed_at = datetime.datetime.utcnow()
                    
                    scraped = j_norm.total_scraped or 0
                    saved = j_norm.total_saved or 0
                    duplicates = j_norm.total_duplicates or 0
                    failed = j_norm.total_failed or 0
                    skipped = j_norm.total_skipped or 0
                    
                    processed = saved + duplicates + skipped + failed
                    if processed < scraped:
                        skipped += scraped - processed
                        j_norm.total_skipped = skipped
                        
                    db_norm.commit()
            finally:
                db_norm.close()
            
        except Exception as e:
            logger.error(f"Error executing job {job_id}: {e}")
            update_job_stats(job_id, status=JOB_FAILED)


    def _process_leads(self, job_id, campaign_id, location, limit, scraper, query, should_stop):
        """
        Process leads from scraper and save them to database using a safe local session.
        """
        scraped_results = scraper.scrape(query=query, limit=limit, location=location, should_stop=should_stop)
        if scraped_results is None:
            logger.warning(f"Scraper returned None for query: {query}")
            return
            
        # Create a fresh local session for saving leads because the scraper might have taken a long time
        # causing the outer session to become stale or timeout.
        local_db = SessionLocal()
        try:
            local_lead_repo = LeadRepository(local_db)
            local_deduplicator = Deduplicator(local_lead_repo)
            
            for lead_data in scraped_results:
                if should_stop(): 
                    break
                
                if lead_data.get("meta_event") == "loaded":
                    update_job_stats(job_id, loaded_count=lead_data.get("count", 0))
                    continue
                
                update_job_stats(job_id, scraped_delta=1)

                business_name = lead_data.get("business_name", "")
                source_url = lead_data.get("google_maps_url", "")
                if not source_url:
                    source_url = lead_data.get("raw_data", {}).get("source_url", "")

                if is_fake_business_name(business_name, query):
                    logger.info(f"Skipping lead due to fake business name: {business_name}")
                    update_job_stats(job_id, skipped_delta=1)
                    continue

                if is_invalid_source_url(source_url):
                    logger.info(f"Skipping lead due to invalid source URL: {source_url}")
                    update_job_stats(job_id, skipped_delta=1)
                    continue

                from modules.dork_optimizer.dork_filters import is_low_quality_dork_url
                website_url = lead_data.get('website') or lead_data.get('google_maps_url')
                if website_url and is_low_quality_dork_url(website_url, exclude_directories=True):
                    logger.info(f"Skipping low quality dork URL: {website_url}")
                    update_job_stats(job_id, skipped_delta=1)
                    continue

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
                        
                if lead_data.get('phone'):
                    lead_data['has_phone'] = True
                if lead_data.get('website'):
                    lead_data['has_website'] = True

                if local_deduplicator.is_duplicate(lead_data):
                    update_job_stats(job_id, duplicate_delta=1)
                    continue
                    
                from modules.dork_optimizer.dork_filters import calculate_lead_quality_score
                lead_quality_score = calculate_lead_quality_score(lead_data)
                
                dork_type = None
                opportunity_id = None
                try:
                    from modules.database.models import GeneratedDork as G_Dork
                    d_record = local_db.query(G_Dork).filter(G_Dork.dork == query).first()
                    if d_record:
                        dork_type = d_record.dork_type
                        opportunity_id = d_record.opportunity_id
                except Exception:
                    pass
                    
                lead_data["raw_data"] = lead_data.get("raw_data") or {}
                lead_data["raw_data"]["dork_quality_score"] = lead_quality_score
                lead_data["raw_data"]["original_dork"] = query
                lead_data["raw_data"]["source"] = "dork_optimizer"
                if dork_type:
                    lead_data["raw_data"]["dork_type"] = dork_type
                if opportunity_id:
                    lead_data["raw_data"]["opportunity_id"] = opportunity_id
                    
                try:
                    if d_record:
                        lead_data["source"] = "serper_bulk_dork"
                except NameError:
                    pass

                try:
                    local_lead_repo.create(
                        campaign_id=campaign_id,
                        scraping_job_id=job_id,
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
                        rating=safe_float(lead_data.get('rating')),
                        reviews_count=safe_int(lead_data.get('reviews_count')),
                        raw_data=lead_data.get('raw_data', {})
                    )
                    update_job_stats(job_id, saved_delta=1)
                except Exception as e:
                    logger.error(f"Error saving lead: {e}")
                    local_db.rollback()

                yield lead_data
        finally:
            local_db.close()
