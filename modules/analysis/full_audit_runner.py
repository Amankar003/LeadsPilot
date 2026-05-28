"""
full_audit_runner.py - Orchestrates the entire lead audit process.
"""
import time
import httpx
from config.database import SessionLocal
from modules.database.models import Lead
from utils.logging_utils import get_logger

from .website_detector import detect_website
from .seo_auditor import audit_seo
from .cta_detector import audit_cta
from .responsive_auditor import audit_responsive
from .speed_auditor import audit_speed
from .broken_link_checker import audit_broken_links
from .security_auditor import audit_security
from .trust_signal_detector import audit_trust_signals
from .app_requirement_detector import detect_app_requirement
from .scoring_engine import calculate_scores
from .pain_point_engine import generate_pain_points
from .service_recommendation_engine import generate_recommendations
from .ai_report_generator import generate_ai_report

logger = get_logger(__name__)

def run_full_lead_audit(lead: Lead) -> dict:
    """
    Runs the complete hybrid audit process for a lead.
    Returns structured results including AI report.
    """
    start_time = time.time()
    logger.info(f"Starting full audit for lead: {lead.business_name} (URL: {lead.website})")
    
    # 1. Website Detection
    site_info = detect_website(lead.website)
    
    audit_data = {
        "lead_info": {
            "name": lead.business_name,
            "category": lead.category,
            "phone": lead.phone,
            "email": lead.email,
        },
        "has_website": site_info["has_website"],
        "site_info": site_info,
        "seo": {},
        "cta": {},
        "responsive": {},
        "speed": {},
        "broken_links": {},
        "security": {},
        "trust": {},
        "app_requirement": {},
        "has_phone": bool(lead.phone),
        "has_email": bool(lead.email)
    }
    
    if site_info["has_website"] and site_info["final_url"]:
        final_url = site_info["final_url"]
        
        # Pre-fetch homepage HTML for local parsing tools to save requests
        try:
            resp = httpx.get(
                final_url, 
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=15.0,
                follow_redirects=True
            )
            html = resp.text
            
            # Run parallelizable HTML-based audits
            audit_data["seo"] = audit_seo(html, final_url)
            audit_data["cta"] = audit_cta(html, final_url)
            audit_data["responsive"] = audit_responsive(html, final_url)
            audit_data["trust"] = audit_trust_signals(html)
            
            # Security (partially uses html)
            audit_data["security"] = audit_security(final_url, html)
            
            # Speed (reuse load time from detection)
            audit_data["speed"] = audit_speed(
                final_url, 
                page_size_bytes=site_info["page_size_bytes"], 
                load_time_ms=site_info["load_time_ms"]
            )
            
            # Broken Links (makes separate network calls, keep it limited)
            audit_data["broken_links"] = audit_broken_links(html, final_url)
            
        except Exception as e:
            logger.error(f"Error fetching HTML for audits on {final_url}: {e}")
            
    # App Requirement (doesn't need website HTML)
    audit_data["app_requirement"] = detect_app_requirement(lead.category, audit_data.get("cta", {}))
    
    # 2. Scoring & Facts Processing
    scores = calculate_scores(audit_data)
    pain_points = generate_pain_points(audit_data)
    recommendations = generate_recommendations(pain_points)
    
    # 3. AI Report Generation
    ai_report = generate_ai_report(audit_data, pain_points, recommendations)
    
    execution_time = time.time() - start_time
    logger.info(f"Audit completed in {execution_time:.2f}s for {lead.business_name}")
    
    return {
        "audit_data": audit_data,
        "scores": scores,
        "pain_points": pain_points,
        "recommendations": recommendations,
        "ai_report": ai_report,
        "execution_time_seconds": execution_time
    }
