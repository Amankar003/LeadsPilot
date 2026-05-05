import time
import logging
import hashlib
import json
from typing import List, Dict, Any, Callable
from sqlalchemy.orm import Session

from modules.scraping.query_expander import generate_query_variations
from modules.scraping.serper_bulk_scraper import fetch_serper_results
from modules.scraping.lead_cleaner import dedupe_serp_results, get_domain
from modules.scraping.website_contact_scraper import scrape_contact_info
from modules.database.repositories import LeadRepository, JobRepository
from modules.database.models import Lead, ScrapingJob
from config.database import SessionLocal
from utils.constants import JOB_STOPPED

logger = logging.getLogger(__name__)

def generate_lead_hash(title: str, url: str, query: str) -> str:
    """Generates a unique hash for a lead to avoid duplicates in DB."""
    raw = f"{title}|{url}|{query}".lower().strip()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def run_bulk_serper_scraping(
    db: Session,
    campaign_id: str,
    job_id: str,
    main_query: str,
    location: str = "",
    target_count: int = 5000, 
    max_query_variations: int = 30,
    max_pages_per_query: int = 10,
    scrape_websites: bool = True,
    progress_callback: Callable = None
) -> dict:
    """
    Orchestrates bulk SERP scraping using Serper.dev and website extraction.
    Saves leads in real-time as they are found.
    """
    summary = {
        "status": "started",
        "queries_processed": 0,
        "pages_processed": 0,
        "raw_results_found": 0,
        "unique_leads_saved": 0,
        "emails_found": 0,
        "phones_found": 0,
        "errors": []
    }

    def is_stopped():
        thread_db = SessionLocal()
        try:
            job = thread_db.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
            return job and job.status == JOB_STOPPED
        finally:
            thread_db.close()

    try:
        # 1. Expand Queries
        queries = generate_query_variations(main_query, location, limit=max_query_variations)
        logger.info(f"Generated {len(queries)} query variations for: {main_query}")
        
        lead_repo = LeadRepository(db)
        job_repo = JobRepository(db)
        
        seen_urls = set()
        
        # 2. Loop through queries
        for q_idx, query in enumerate(queries):
            if is_stopped():
                logger.info("Stopping bulk scraping as per user request.")
                break

            if progress_callback:
                progress_callback(f"Processing query {q_idx+1}/{len(queries)}: {query}", (q_idx / len(queries)) * 0.5)

            # 3. Loop through pages
            for page in range(1, max_pages_per_query + 1):
                if is_stopped(): break
                
                results = fetch_serper_results(query, page=page)
                if not results:
                    break # No more results for this query
                
                summary["raw_results_found"] += len(results)
                summary["pages_processed"] += 1
                
                # Update job stats in DB for scraping count
                job_repo.update_status(job_id, "RUNNING", total_scraped=summary["raw_results_found"])
                
                # 4. Clean and Dedupe CURRENT page results
                unique_page_results = dedupe_serp_results(results)
                
                # 5. Process and Save Leads IMMEDIATELY
                for res in unique_page_results:
                    if is_stopped(): break
                    
                    link = res.get("link", "")
                    if not link or link in seen_urls:
                        continue
                    seen_urls.add(link)
                    
                    title = res.get("title", "Unknown Business")
                    snippet = res.get("snippet", "")
                    l_hash = generate_lead_hash(title, link, main_query)
                    
                    # Check DB duplicate
                    if lead_repo.check_duplicate(lead_hash=l_hash):
                        summary.setdefault("total_duplicates", 0)
                        summary["total_duplicates"] += 1
                        job_repo.update_status(job_id, "RUNNING", total_duplicates=summary["total_duplicates"])
                        logger.debug(f"Lead already exists: {title}")
                        continue
                    
                    contact_info = {
                        "emails": [],
                        "phones": [],
                        "whatsapp_links": [],
                        "social_links": [],
                        "contact_page": "",
                        "website_status": "active",
                        "scraped_text_snippet": snippet
                    }

                    # 6. Scrape Website (Enrichment)
                    is_irrelevant = res.get("is_irrelevant", False)
                    is_dir = res.get("is_directory", False)
                    is_soc = res.get("is_social", False)
                    
                    if not scrape_websites:
                        contact_info["website_status"] = "skipped_by_user"
                    elif is_irrelevant:
                        contact_info["website_status"] = "skipped_irrelevant_domain"
                    elif is_dir or is_soc:
                        contact_info["website_status"] = "skipped_directory_or_social"
                    else:
                        logger.info(f"Scraping website: {link}")
                        contact_info = scrape_contact_info(link)
                        time.sleep(0.5) 
                    
                    # 7. Prepare and Save
                    email = contact_info["emails"][0] if contact_info.get("emails") else None
                    phone = contact_info["phones"][0] if contact_info.get("phones") else None
                    
                    has_name = bool(title)
                    has_phone = bool(phone)
                    has_email = bool(email)
                    has_website = bool(link)
                    has_address = bool(location)
                    
                    if has_name and (has_phone or has_email or has_website or has_address):
                        lead_data = {
                            "campaign_id": campaign_id,
                            "scraping_job_id": job_id,
                            "business_name": title,
                            "category": main_query,
                            "phone": phone,
                            "email": email,
                            "website": link,
                            "address": location,
                            "source": "serper_bulk",
                            "lead_hash": l_hash,
                            "has_email": has_email,
                            "has_phone": has_phone,
                            "has_website": has_website,
                            "raw_data": {
                                **res,
                                **contact_info
                            }
                        }
                        
                        try:
                            lead_repo.create(**lead_data)
                            summary["unique_leads_saved"] += 1
                            if email: summary["emails_found"] += 1
                            if phone: summary["phones_found"] += 1
                            
                            # Update job stats in DB real-time for saved count
                            job_repo.update_status(job_id, "RUNNING", total_saved=summary["unique_leads_saved"])
                            logger.info(f"✅ Saved Lead ({summary['unique_leads_saved']}): {title}")
                        except Exception as e:
                            logger.error(f"❌ DATABASE SAVE FAILED for {title}: {str(e)}")
                            summary["errors"].append(f"Save error: {title}")
                    else:
                        logger.warning(f"⚠️ Skipped lead {title}: Missing contact info.")
                    
                time.sleep(1) # Rate limit per page
                
            summary["queries_processed"] += 1

        if is_stopped():
            summary["status"] = "stopped"
            job_repo.update_status(job_id, "STOPPED", 
                                 total_scraped=summary["raw_results_found"],
                                 total_saved=summary["unique_leads_saved"])
        else:
            summary["status"] = "completed"
            job_repo.update_status(job_id, "COMPLETED", 
                                 total_scraped=summary["raw_results_found"],
                                 total_saved=summary["unique_leads_saved"])

    except Exception as e:
        logger.error(f"Bulk scraping failed: {str(e)}")
        summary["status"] = "failed"
        summary["errors"].append(str(e))
        job_repo.update_status(job_id, "FAILED", error_message=str(e))

    return summary
