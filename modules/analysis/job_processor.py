"""
job_processor.py - Database-based queue for analysis jobs without Redis.
"""
import time
import threading
import traceback
from datetime import datetime, timedelta
from config.database import SessionLocal
from modules.database.models import AnalysisJob, AnalysisReport, PainPoint, RecommendedService, Lead
from modules.analysis.full_audit_runner import run_full_lead_audit
from utils.logging_utils import get_logger

logger = get_logger(__name__)

# Maximum concurrent worker threads processing analysis jobs
MAX_CONCURRENT_JOBS = int(getattr(__import__('os'), 'environ', {}).get('MAX_CONCURRENT_JOBS', 3))

# Processor thread state
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
        AnalysisJob.status.in_("PENDING,RUNNING".split(","))
    ).first()

    if existing_job:
        return False

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return False

    job = AnalysisJob(
        lead_id=lead_id,
        website_url=lead.website,
        status="PENDING",
    )
    db.add(job)
    db.commit()

    # Ensure processor is running
    start_processor_thread()
    return True


def _execute_job(job_id: str):
    """Execute a single analysis job in its own thread and DB session."""
    db = SessionLocal()
    try:
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if not job:
            logger.warning(f"Job {job_id} not found when trying to execute.")
            return

        # Ensure job is marked running
        job.status = "RUNNING"
        if not job.started_at:
            job.started_at = datetime.utcnow()
        db.commit()

        logger.info(f"Started job execution {job.id} for lead {job.lead_id}")

        lead = db.query(Lead).filter(Lead.id == job.lead_id).first()
        if not lead:
            raise RuntimeError(f"Lead not found for job {job.id}")

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
            ai_report_json=results["ai_report"],
        )
        db.add(report)
        db.commit()

        # 2. Save Pain Points individually
        try:
            for pp in results.get("pain_points", []):
                db.add(PainPoint(
                    lead_id=lead.id,
                    job_id=job.id,
                    type=pp.get("type"),
                    severity=pp.get("severity"),
                    title=pp.get("title"),
                    description=pp.get("description"),
                    evidence=pp.get("evidence"),
                    business_impact=pp.get("business_impact"),
                    recommended_service=pp.get("recommended_service"),
                ))
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to add pain points for job {job.id}. Missing column (job_id)?: {e}")

        # 3. Save Recommendations individually
        try:
            for rec in results.get("recommendations", []):
                db.add(RecommendedService(
                    lead_id=lead.id,
                    job_id=job.id,
                    service_name=rec.get("service_name"),
                    priority=rec.get("priority"),
                    reason=rec.get("reason"),
                    pitch_angle=rec.get("pitch_angle"),
                ))
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to add recommendations for job {job.id}. Missing column (job_id)?: {e}")

        # 4. Mark job completed
        try:
            job = db.query(AnalysisJob).filter(AnalysisJob.id == job.id).first()
            if job:
                job.status = "COMPLETED"
                job.completed_at = datetime.utcnow()
                db.commit()
                logger.info(f"Completed analysis job {job.id}")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark job as COMPLETED {job.id}: {e}")

        # 5. Auto-generate outreach and save CRM draft (best-effort)
        try:
            from modules.analysis.outreach_generator import generate_outreach
            from modules.database.repositories import OutreachMessageRepository, EmailDraftRepository

            # Refresh report from DB to ensure relationships
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
                outrepo.create(
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

                # Save a CRM draft if none exists for this lead
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
                    db.commit()

        except Exception as e:
            logger.error(f"Failed to auto-generate outreach for report {getattr(report, 'id', 'unknown')}: {e}\n{traceback.format_exc()}")

    except Exception as e:
        db.rollback()
        logger.error(f"Error executing analysis job {job_id}: {e}\n{traceback.format_exc()}")
        try:
            job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
            if job:
                job.status = "FAILED"
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                db.commit()
        except Exception:
            db.rollback()
            logger.exception(f"Failed to mark job {job_id} as FAILED")
    finally:
        db.close()


def _process_queue():
    """Background thread that polls the DB and spawns worker threads for pending jobs."""
    global _is_processing
    _is_processing = True

    try:
        while True:
            db = SessionLocal()
            try:
                # Count currently running jobs
                running_count = db.query(AnalysisJob).filter(AnalysisJob.status == "RUNNING").count()

                if running_count >= MAX_CONCURRENT_JOBS:
                    db.close()
                    time.sleep(2)
                    continue

                # Get next pending job
                job = db.query(AnalysisJob).filter(AnalysisJob.status == "PENDING").order_by(
                    AnalysisJob.priority.desc(), AnalysisJob.created_at.asc()
                ).first()

                if not job:
                    db.close()
                    time.sleep(3)
                    continue

                # Mark as running and spawn a worker thread to execute the job
                job.status = "RUNNING"
                job.started_at = datetime.utcnow()
                db.commit()

                logger.info(f"Spawning worker for analysis job {job.id} (lead {job.lead_id})")
                t = threading.Thread(target=_execute_job, args=(job.id,), daemon=True)
                t.start()

            except Exception as e:
                logger.error(f"Queue processor error: {e}\n{traceback.format_exc()}")
            finally:
                try:
                    db.close()
                except Exception:
                    pass

            time.sleep(1)

    finally:
        _is_processing = False


def recover_stuck_jobs(timeout_minutes: int = 30):
    """Find RUNNING jobs older than `timeout_minutes` and mark them FAILED/TIMEOUT."""
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        stuck_jobs = db.query(AnalysisJob).filter(
            AnalysisJob.status == "RUNNING",
            AnalysisJob.updated_at < cutoff,
        ).all()

        for job in stuck_jobs:
            try:
                job.status = "FAILED"
                job.error_message = f"Job timed out after {timeout_minutes} minutes"
                job.completed_at = datetime.utcnow()
                db.commit()
                logger.warning(f"Marked stuck job {job.id} as FAILED due to timeout")
            except Exception:
                db.rollback()
                logger.exception(f"Failed to mark stuck job {job.id}")
    finally:
        db.close()


def start_processor_thread():
    """Starts the queue processor thread if not already running and runs recovery."""
    global _processor_thread, _is_processing
    # Run recovery first
    try:
        recover_stuck_jobs()
    except Exception:
        logger.exception("Error during stuck-job recovery")

    if not _is_processing or (_processor_thread and not _processor_thread.is_alive()):
        _processor_thread = threading.Thread(target=_process_queue, daemon=True)
        _processor_thread.start()
        logger.info("Started analysis queue processor thread")
