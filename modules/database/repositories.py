from sqlalchemy.orm import Session
from modules.database.models import Campaign, ScrapingJob, Lead, LeadInsight, EmailDraft, EmailLog, SuppressionList, FollowUp, CRMActivity

class CampaignRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        campaign = Campaign(**kwargs)
        self.db.add(campaign)
        self.db.commit()
        self.db.refresh(campaign)
        return campaign

    def get_all(self):
        return self.db.query(Campaign).order_by(Campaign.created_at.desc()).all()
        
    def get_by_id(self, campaign_id: str):
        return self.db.query(Campaign).filter(Campaign.id == campaign_id).first()

class JobRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        job = ScrapingJob(**kwargs)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get_all(self):
        return self.db.query(ScrapingJob).order_by(ScrapingJob.created_at.desc()).all()
        
    def update_status(self, job_id: str, status: str, **kwargs):
        job = self.db.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
        if job:
            job.status = status
            for key, value in kwargs.items():
                setattr(job, key, value)
            self.db.commit()
            self.db.refresh(job)
        return job

class LeadRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        lead = Lead(**kwargs)
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead
        
    def check_duplicate(self, email=None, phone=None, website=None, lead_hash=None):
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
            
        # Or conditions
        from sqlalchemy import or_
        existing = query.filter(or_(*conditions)).first()
        return existing is not None

    def get_all(self):
        return self.db.query(Lead).order_by(Lead.created_at.desc()).all()

    def update_status(self, lead_id: str, status: str):
        lead = self.db.query(Lead).filter(Lead.id == lead_id).first()
        if lead:
            lead.status = status
            self.db.commit()
            self.db.refresh(lead)
        return lead

class LeadInsightRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        insight = LeadInsight(**kwargs)
        self.db.add(insight)
        self.db.commit()
        self.db.refresh(insight)
        return insight
        
    def get_by_lead_id(self, lead_id: str):
        return self.db.query(LeadInsight).filter(LeadInsight.lead_id == lead_id).first()

class EmailDraftRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        draft = EmailDraft(**kwargs)
        self.db.add(draft)
        self.db.commit()
        self.db.refresh(draft)
        return draft
        
    def get_by_id(self, draft_id: str):
        return self.db.query(EmailDraft).filter(EmailDraft.id == draft_id).first()
        
    def get_by_lead_id(self, lead_id: str):
        return self.db.query(EmailDraft).filter(EmailDraft.lead_id == lead_id).all()
        
    def get_by_campaign_id(self, campaign_id: str):
        return self.db.query(EmailDraft).filter(EmailDraft.campaign_id == campaign_id).all()
        
    def update(self, draft_id: str, **kwargs):
        draft = self.get_by_id(draft_id)
        if draft:
            for key, value in kwargs.items():
                setattr(draft, key, value)
            self.db.commit()
            self.db.refresh(draft)
        return draft

class EmailLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        log = EmailLog(**kwargs)
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log
        
    def get_by_lead_id(self, lead_id: str):
        return self.db.query(EmailLog).filter(EmailLog.lead_id == lead_id).all()

    def get_all(self):
        return self.db.query(EmailLog).order_by(EmailLog.created_at.desc()).all()

class SuppressionListRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        item = SuppressionList(**kwargs)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item
        
    def check_email(self, email: str):
        if not email:
            return False
        return self.db.query(SuppressionList).filter(SuppressionList.email == email).first() is not None

class FollowUpRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        fup = FollowUp(**kwargs)
        self.db.add(fup)
        self.db.commit()
        self.db.refresh(fup)
        return fup
        
    def get_pending(self):
        return self.db.query(FollowUp).filter(FollowUp.status == "PENDING").all()

class CRMActivityRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs):
        activity = CRMActivity(**kwargs)
        self.db.add(activity)
        self.db.commit()
        self.db.refresh(activity)
        return activity
        
    def get_by_lead_id(self, lead_id: str):
        return self.db.query(CRMActivity).filter(CRMActivity.lead_id == lead_id).order_by(CRMActivity.created_at.desc()).all()
