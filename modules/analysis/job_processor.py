"""
job_processor.py - Database-based queue for analysis jobs without Redis.
"""
import time
import threading
from datetime import datetime
from config.database import SessionLocal
from modules.database.models import AnalysisJob, AnalysisReport, PainPoint, RecommendedService, Lead
from modules.analysis.full_audit_runner import run_full_lead_audit
from utils.logging_utils import get_logger

logger = get_logger(__name__)

MAX_CONCURRENT_JOBS = 3
_is_processing = False
_processor_thread = None

def get_job_status(db, lead_id: str):
    """Get the current analysis job status for a lead."""
    return db.query(AnalysisJob).filter(
        AnalysisJob.lead_id == lead_id
    ).order_by(AnalysisJob.created_at.desc()).first()

def get_report(db, lead_id: str):
    """Get the generated report for a lead."""
    return db.query(AnalysisReport).filter(
        AnalysisReport.lead_id == lead_id
    ).order_by(AnalysisReport.created_at.desc()).first()

def queue_analysis_job(db, lead_id: str) -> bool:
    """
    Queue a new analysis job for a lead.
    Returns True if successfully queued, False if already running/pending.
    """
    existing_job = db.query(AnalysisJob).filter(
        AnalysisJob.lead_id == lead_id,
        AnalysisJob.status.in_(["PENDING", "RUNNING"])
    ).first()
    
    if existing_job:
        return False
        
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return False
        
    job = AnalysisJob(
        lead_id=lead_id,
        website_url=lead.website,
        status="PENDING"
    )
    db.add(job)
    db.commit()
    
    start_processor_thread()
    return True

def _process_queue():
    """Background thread that processes pending analysis jobs."""
    global _is_processing
    _is_processing = True
    
    try:
        while True:
            db = SessionLocal()
            try:
                # Count currently running jobs
                running_count = db.query(AnalysisJob).filter(AnalysisJob.status == "RUNNING").count()
                
                if running_count >= MAX_CONCURRENT_JOBS:
                    time.sleep(5)
                    continue
                    
                # Get next pending job
                job = db.query(AnalysisJob).filter(
                    AnalysisJob.status == "PENDING"
                ).order_by(
                    AnalysisJob.priority.desc(),
                    AnalysisJob.created_at.asc()
                ).first()
                
                if not job:
                    break # Queue empty
                    
                # Mark as running
                job.status = "RUNNING"
                job.started_at = datetime.utcnow()
                db.commit()
                
                logger.info(f"Processing analysis job {job.id} for lead {job.lead_id}")
                
                try:
                    lead = db.query(Lead).filter(Lead.id == job.lead_id).first()
                    results = run_full_lead_audit(lead)
                    
                    # 1. Save Report
                    report = AnalysisReport(
                        lead_id=lead.id,
                        job_id=job.id,
                        website_url=lead.website,
                        has_website=results["audit_data"].get("has_website", False),
                        overall_score=results["scores"].get("overall_score", 0),
                        opportunity_score=results["scores"].get("opportunity_score", 0),
                        opportunity_level=results["scores"].get("opportunity_level", "Low"),
                        raw_audit_json=results["audit_data"],
                        pain_points_json=results["pain_points"],
                        recommended_services_json=results["recommendations"],
                        ai_report_json=results["ai_report"]
                    )
                    db.add(report)
                    
                    # 2. Save Pain Points individually
                    for pp in results["pain_points"]:
                        db.add(PainPoint(
                            lead_id=lead.id,
                            job_id=job.id,
                            type=pp["type"],
                            severity=pp["severity"],
                            title=pp["title"],
                            description=pp["description"],
                            evidence=pp["evidence"],
                            business_impact=pp["business_impact"],
                            recommended_service=pp["recommended_service"]
                        ))
                        
                    # 3. Save Recommendations individually
                    for rec in results["recommendations"]:
                        db.add(RecommendedService(
                            lead_id=lead.id,
                            job_id=job.id,
                            service_name=rec["service_name"],
                            priority=rec["priority"],
                            reason=rec["reason"],
                            pitch_angle=rec["pitch_angle"]
                        ))
                        
                    # 4. Mark job completed
                    job.status = "COMPLETED"
                    job.completed_at = datetime.utcnow()
                    db.commit()
                    logger.info(f"Successfully completed analysis job {job.id}")

                    # 5. Auto-generate outreach and save CRM draft
                    try:
                        from modules.analysis.outreach_generator import generate_outreach
                        from modules.database.repositories import OutreachMessageRepository, EmailDraftRepository

                        # Ensure report is refreshed from DB
                        db.refresh(report)

                        outreach_result = generate_outreach(
                            report=report,
                            lead=lead,
                            email_type="Cold Outreach",
                            tone="Professional",
                            length="Short",
                            cta_goal="Get Reply",
                            service_focus="Auto (from report)",
                        )

                        if outreach_result and "error" not in outreach_result:
                            outrepo = OutreachMessageRepository(db)
                            latest_msg = outrepo.create(
                                lead_id=lead.id,
                                report_id=report.id,
                                email_type="Cold Outreach",
                                tone="Professional",
                                length="Short",
                                cta_goal="Get Reply",
                                service_focus="Auto (from report)",
                                subject_lines=outreach_result.get("subject_lines", []),
                                email_body=outreach_result.get("email_body", ""),
                                whatsapp_message=outreach_result.get("whatsapp_message", ""),
                                linkedin_message=outreach_result.get("linkedin_message", ""),
                                follow_up_1=outreach_result.get("follow_up_1", ""),
                                follow_up_2=outreach_result.get("follow_up_2", ""),
                            )

                            # Save CRM draft if none exists for this lead
                            draft_repo = EmailDraftRepository(db)
                            existing_drafts = draft_repo.get_by_lead_id(lead.id)
                            if not existing_drafts:
                                draft_repo.create(
                                    lead_id=lead.id,
                                    campaign_id=lead.campaign_id,
                                    subject=outreach_result.get("subject_lines", [f"Ideas for {lead.business_name}"])[0],
                                    body=outreach_result.get("email_body", ""),
                                    preview_text=outreach_result.get("preview_text", report.ai_report_json.get("main_pitch_angle", "")),
                                    identified_problem=outreach_result.get("identified_problem", "Audit-based"),
                                    proposed_solution=outreach_result.get("proposed_solution", "Audit-based"),
                                    personalization_used=outreach_result.get("personalization_used", "Website Audit + AI"),
                                    confidence_score=outreach_result.get("confidence_score", "High"),
                                    email_type="Cold Outreach",
                                    generated_by_model="groq_outreach_generator",
                                )
                    except Exception as e:
                        logger.error(f"Failed to auto-generate outreach for report {getattr(report, 'id', 'unknown')}: {e}")
                    
                except Exception as e:
                    logger.error(f"Error processing analysis job {job.id}: {e}")
                    db.rollback()
                    
                    job = db.query(AnalysisJob).filter(AnalysisJob.id == job.id).first()
                    job.status = "FAILED"
                    job.error_message = str(e)
                    job.completed_at = datetime.utcnow()
                    db.commit()
                    
            except Exception as e:
                logger.error(f"Queue processor error: {e}")
            finally:
                db.close()
                
            time.sleep(2) # Small delay between jobs
            
    finally:
        _is_processing = False

def start_processor_thread():
    """Starts the queue processor thread if not already running."""
    global _processor_thread, _is_processing
    if not _is_processing or (_processor_thread and not _processor_thread.is_alive()):
        _processor_thread = threading.Thread(target=_process_queue, daemon=True)
        _processor_thread.start()
        logger.info("Started analysis queue processor thread")
