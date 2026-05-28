import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from modules.database.models import (
    Campaign, ScrapingJob, Lead, Dork, LeadInsight, EmailDraft, 
    EmailLog, SuppressionList, FollowUp, CRMActivity, OutreachMessage
)

logger = logging.getLogger("leadpilot.database")

def safe_read(db: Session, query_fn, *args, **kwargs):
    """
    Safely executes a read-only database query with retry-once logic on OperationalError.
    """
    try:
        result = query_fn(*args, **kwargs)
        # Detach loaded model instances so they remain safe after the session closes.
        try:
            db.expunge_all()
        except Exception as exc:
            logger.debug(f"Failed to expunge loaded rows: {exc}")
        return result
    except OperationalError as e:
        db.rollback()
        logger.warning("Database connection lost. Retrying read query once...")
        try:
            result = query_fn(*args, **kwargs)
            try:
                db.expunge_all()
            except Exception as exc:
                logger.debug(f"Failed to expunge loaded rows on retry: {exc}")
            return result
        except Exception as retry_ex:
            logger.error("Database retry failed.")
            db.rollback()
            raise retry_ex
    except SQLAlchemyError as e:
        db.rollback()
        raise e

def safe_write(db: Session, write_fn, *args, **kwargs):
    """
    Safely executes a database write with rollback on any exception.
    No blind retries for safety.
    """
    try:
        return write_fn(*args, **kwargs)
    except Exception as e:
        db.rollback()
        logger.error(f"Database write operation failed, rolled back: {e}")
        raise e

def safe_int(value, default=0):
    if isinstance(value, tuple):
        value = value[0] if value else default
    try:
        return int(value)
    except Exception:
        return default

class CampaignRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        # Sanitize numeric fields using safe_int
        limit = safe_int(kwargs.get("limit"), 100)
        max_fallback_results = safe_int(kwargs.get("max_fallback_results"), 5)
        max_fallback_pages = safe_int(kwargs.get("max_fallback_pages"), 2)

        # Print value and type before DB insert
        print("limit:", limit, type(limit))
        print("max_fallback_results:", max_fallback_results, type(max_fallback_results))
        print("max_fallback_pages:", max_fallback_pages, type(max_fallback_pages))

        kwargs["limit"] = limit
        kwargs["max_fallback_results"] = max_fallback_results
        kwargs["max_fallback_pages"] = max_fallback_pages

        def _write():
            if "user_id" not in kwargs or not kwargs["user_id"]:
                from modules.database.models import get_or_create_default_user
                user = get_or_create_default_user(self.db)
                kwargs["user_id"] = user.id
            campaign = Campaign(**kwargs)
            self.db.add(campaign)
            self.db.commit()
            self.db.refresh(campaign)
            return campaign
        return safe_write(self.db, _write)

    def get_all(self):
        return safe_read(self.db, lambda: self.db.query(Campaign).order_by(Campaign.created_at.desc()).all())
        
    def get_by_id(self, campaign_id: str):
        return safe_read(self.db, lambda: self.db.query(Campaign).filter(Campaign.id == campaign_id).first())

class JobRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        def _write():
            job = ScrapingJob(**kwargs)
            self.db.add(job)
            self.db.commit()
            self.db.refresh(job)
            return job
        return safe_write(self.db, _write)

    def get_all(self):
        return safe_read(self.db, lambda: self.db.query(ScrapingJob).order_by(ScrapingJob.created_at.desc()).all())
        
    def update_status(self, job_id: str, status: str, **kwargs):
        def _write():
            job = self.db.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
            if job:
                job.status = status
                for key, value in kwargs.items():
                    setattr(job, key, value)
                self.db.commit()
                self.db.refresh(job)
            return job
        return safe_write(self.db, _write)

class LeadRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        def _write():
            lead_hash = kwargs.get("lead_hash")
            if lead_hash:
                existing = self.db.query(Lead).filter(Lead.lead_hash == lead_hash).first()
                if existing:
                    return existing
            if "user_id" not in kwargs or not kwargs["user_id"]:
                from modules.database.models import get_or_create_default_user
                user = get_or_create_default_user(self.db)
                kwargs["user_id"] = user.id
            lead = Lead(**kwargs)
            self.db.add(lead)
            self.db.commit()
            self.db.refresh(lead)
            return lead
        return safe_write(self.db, _write)
    
    def get_by_lead_hash(self, lead_hash: str):
        return safe_read(self.db, lambda: self.db.query(Lead).filter(Lead.lead_hash == lead_hash).first())

    def update(self, lead_id: str, **kwargs):
        def _write():
            lead = self.db.query(Lead).filter(Lead.id == lead_id).first()
            if lead:
                for key, value in kwargs.items():
                    setattr(lead, key, value)
                self.db.commit()
                self.db.refresh(lead)
            return lead
        return safe_write(self.db, _write)
        
    def check_duplicate(self, email=None, phone=None, website=None, lead_hash=None):
        def _query():
            query = self.db.query(Lead)
            conditions = []
            if email:
                conditions.append(Lead.email == email)
            if phone:
                conditions.append(Lead.phone == phone)
            if website:
                conditions.append(Lead.website == website)
            if lead_hash:
                conditions.append(Lead.lead_hash == lead_hash)
                
            if not conditions:
                return False
                
            from sqlalchemy import or_
            existing = query.filter(or_(*conditions)).first()
            return existing is not None
        return safe_read(self.db, _query)

    def get_all(self):
        return safe_read(self.db, lambda: self.db.query(Lead).order_by(Lead.created_at.desc()).all())

    def update_status(self, lead_id: str, status: str):
        def _write():
            lead = self.db.query(Lead).filter(Lead.id == lead_id).first()
            if lead:
                lead.status = status
                self.db.commit()
                self.db.refresh(lead)
            return lead
        return safe_write(self.db, _write)

class LeadInsightRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        def _write():
            insight = LeadInsight(**kwargs)
            self.db.add(insight)
            self.db.commit()
            self.db.refresh(insight)
            return insight
        return safe_write(self.db, _write)
        
    def get_by_lead_id(self, lead_id: str):
        return safe_read(self.db, lambda: self.db.query(LeadInsight).filter(LeadInsight.lead_id == lead_id).first())

class EmailDraftRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        def _write():
            if "user_id" not in kwargs or not kwargs["user_id"]:
                from modules.database.models import get_or_create_default_user
                user = get_or_create_default_user(self.db)
                kwargs["user_id"] = user.id
            draft = EmailDraft(**kwargs)
            self.db.add(draft)
            self.db.commit()
            self.db.refresh(draft)
            return draft
        return safe_write(self.db, _write)
        
    def get_by_id(self, draft_id: str):
        return safe_read(self.db, lambda: self.db.query(EmailDraft).filter(EmailDraft.id == draft_id).first())
        
    def get_by_lead_id(self, lead_id: str):
        return safe_read(self.db, lambda: self.db.query(EmailDraft).filter(EmailDraft.lead_id == lead_id).all())
        
    def get_by_campaign_id(self, campaign_id: str):
        return safe_read(self.db, lambda: self.db.query(EmailDraft).filter(EmailDraft.campaign_id == campaign_id).all())
        
    def update(self, draft_id: str, **kwargs):
        def _write():
            draft = self.db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
            if draft:
                for key, value in kwargs.items():
                    setattr(draft, key, value)
                self.db.commit()
                self.db.refresh(draft)
            return draft
        return safe_write(self.db, _write)

class EmailLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        def _write():
            if "user_id" not in kwargs or not kwargs["user_id"]:
                from modules.database.models import get_or_create_default_user
                user = get_or_create_default_user(self.db)
                kwargs["user_id"] = user.id
            log = EmailLog(**kwargs)
            self.db.add(log)
            self.db.commit()
            self.db.refresh(log)
            return log
        return safe_write(self.db, _write)
        
    def get_by_lead_id(self, lead_id: str):
        return safe_read(self.db, lambda: self.db.query(EmailLog).filter(EmailLog.lead_id == lead_id).all())

    def get_all(self):
        return safe_read(self.db, lambda: self.db.query(EmailLog).order_by(EmailLog.created_at.desc()).all())

class SuppressionListRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        def _write():
            item = SuppressionList(**kwargs)
            self.db.add(item)
            self.db.commit()
            self.db.refresh(item)
            return item
        return safe_write(self.db, _write)
        
    def check_email(self, email: str):
        def _query():
            if not email:
                return False
            return self.db.query(SuppressionList).filter(SuppressionList.email == email).first() is not None
        return safe_read(self.db, _query)

class FollowUpRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        def _write():
            fup = FollowUp(**kwargs)
            self.db.add(fup)
            self.db.commit()
            self.db.refresh(fup)
            return fup
        return safe_write(self.db, _write)
        
    def get_pending(self):
        return safe_read(self.db, lambda: self.db.query(FollowUp).filter(FollowUp.status == "PENDING").all())

class CRMActivityRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        def _write():
            activity = CRMActivity(**kwargs)
            self.db.add(activity)
            self.db.commit()
            self.db.refresh(activity)
            return activity
        return safe_write(self.db, _write)
        
    def get_by_lead_id(self, lead_id: str):
        return safe_read(self.db, lambda: self.db.query(CRMActivity).filter(CRMActivity.lead_id == lead_id).order_by(CRMActivity.created_at.desc()).all())

class OutreachMessageRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        def _write():
            msg = OutreachMessage(**kwargs)
            self.db.add(msg)
            self.db.commit()
            self.db.refresh(msg)
            return msg
        return safe_write(self.db, _write)

    def get_by_lead_id(self, lead_id: str):
        return safe_read(self.db, lambda: self.db.query(OutreachMessage).filter(
            OutreachMessage.lead_id == lead_id
        ).order_by(OutreachMessage.created_at.desc()).all())

    def get_latest_for_lead(self, lead_id: str):
        return safe_read(self.db, lambda: self.db.query(OutreachMessage).filter(
            OutreachMessage.lead_id == lead_id
        ).order_by(OutreachMessage.created_at.desc()).first())

class DorkRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        def _write():
            d = Dork(**kwargs)
            self.db.add(d)
            self.db.commit()
            self.db.refresh(d)
            return d
        return safe_write(self.db, _write)

    def get_by_campaign_id(self, campaign_id: str):
        return safe_read(self.db, lambda: self.db.query(Dork).filter(Dork.campaign_id == campaign_id).order_by(Dork.created_at.desc()).all())

    def get_pending_by_campaign_id(self, campaign_id: str):
        return safe_read(self.db, lambda: self.db.query(Dork).filter(Dork.campaign_id == campaign_id, Dork.status == 'pending').order_by(Dork.created_at.asc()).all())

    def count_by_status(self, campaign_id: str, status: str):
        return safe_read(self.db, lambda: self.db.query(Dork).filter(Dork.campaign_id == campaign_id, Dork.status == status).count())

    def update_status(self, dork_id: str, status: str):
        def _write():
            d = self.db.query(Dork).filter(Dork.id == dork_id).first()
            if d:
                d.status = status
                self.db.commit()
                self.db.refresh(d)
            return d
        return safe_write(self.db, _write)

    def approve(self, msg_id: str, approved_subject: str):
        def _write():
            from datetime import datetime
            msg = self.db.query(OutreachMessage).filter(OutreachMessage.id == msg_id).first()
            if msg:
                msg.is_approved = True
                msg.approved_at = datetime.utcnow()
                msg.approved_subject = approved_subject
                self.db.commit()
                self.db.refresh(msg)
            return msg
        return safe_write(self.db, _write)
