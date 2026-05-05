import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from config.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(String, primary_key=True, default=generate_uuid)
    campaign_name = Column(String, nullable=False)
    platform = Column(String, nullable=False)
    category = Column(String, nullable=False)
    location = Column(String, nullable=False)
    limit = Column(Integer, nullable=True, default=100)
    required_fields = Column(JSON, default=list)
    enable_fallback = Column(Boolean, default=True)
    max_fallback_results = Column(Integer, default=5)
    max_fallback_pages = Column(Integer, default=2)
    status = Column(String, default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    jobs = relationship("ScrapingJob", back_populates="campaign")
    leads = relationship("Lead", back_populates="campaign")

class ScrapingJob(Base):
    __tablename__ = "scraping_jobs"

    id = Column(String, primary_key=True, default=generate_uuid)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    platform = Column(String, nullable=False)
    category = Column(String, nullable=False)
    location = Column(String, nullable=False)
    limit = Column(Integer, nullable=True, default=100)
    status = Column(String, default="PENDING")
    enable_fallback = Column(Boolean, default=True)
    max_fallback_results = Column(Integer, default=5)
    max_fallback_pages = Column(Integer, default=2)
    
    total_scraped = Column(Integer, default=0)
    total_saved = Column(Integer, default=0)
    total_duplicates = Column(Integer, default=0)
    total_failed = Column(Integer, default=0)
    
    error_message = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    campaign = relationship("Campaign", back_populates="jobs")
    leads = relationship("Lead", back_populates="job")

class Lead(Base):
    __tablename__ = "leads"

    id = Column(String, primary_key=True, default=generate_uuid)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    scraping_job_id = Column(String, ForeignKey("scraping_jobs.id"), nullable=False)
    
    business_name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    website = Column(String, nullable=True)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    country = Column(String, nullable=True)
    rating = Column(String, nullable=True)
    reviews_count = Column(String, nullable=True)
    source = Column(String, nullable=True)
    google_maps_url = Column(String, nullable=True)
    email_source = Column(String, nullable=True)
    email_confidence = Column(String, nullable=True)
    
    has_email = Column(Boolean, default=False)
    has_phone = Column(Boolean, default=False)
    has_website = Column(Boolean, default=False)
    
    lead_hash = Column(String, nullable=False, unique=True, index=True)
    status = Column(String, default="NEW_LEAD")
    raw_data = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    campaign = relationship("Campaign", back_populates="leads")
    job = relationship("ScrapingJob", back_populates="leads")

class LeadInsight(Base):
    __tablename__ = "lead_insights"
    id = Column(String, primary_key=True, default=generate_uuid)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False)
    recommended_service = Column(String, nullable=True)
    reason = Column(String, nullable=True)
    pain_points = Column(JSON, default=list)
    lead_score = Column(Integer, default=0)
    lead_type = Column(String, nullable=True)
    ai_model = Column(String, nullable=True)
    ai_response = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class EmailDraft(Base):
    __tablename__ = "email_drafts"
    id = Column(String, primary_key=True, default=generate_uuid)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    subject = Column(String, nullable=False)
    body = Column(String, nullable=False)
    preview_text = Column(String, nullable=True)
    identified_problem = Column(String, nullable=True)
    proposed_solution = Column(String, nullable=True)
    personalization_used = Column(String, nullable=True)
    confidence_score = Column(String, nullable=True)
    email_type = Column(String, nullable=True)
    status = Column(String, default="DRAFT")
    generated_by_model = Column(String, nullable=True)
    approved_by_user = Column(Boolean, default=False)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class EmailLog(Base):
    __tablename__ = "email_logs"
    id = Column(String, primary_key=True, default=generate_uuid)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    email_draft_id = Column(String, ForeignKey("email_drafts.id"), nullable=True)
    recipient_email = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(String, nullable=False)
    provider = Column(String, default="sendgrid")
    provider_message_id = Column(String, nullable=True)
    status = Column(String, default="READY")
    sent_at = Column(DateTime, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class SuppressionList(Base):
    __tablename__ = "suppression_list"
    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, nullable=False, unique=True, index=True)
    reason = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class FollowUp(Base):
    __tablename__ = "followups"
    id = Column(String, primary_key=True, default=generate_uuid)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    parent_email_log_id = Column(String, ForeignKey("email_logs.id"), nullable=True)
    followup_number = Column(Integer, default=1)
    subject = Column(String, nullable=False)
    body = Column(String, nullable=False)
    scheduled_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    status = Column(String, default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class CRMActivity(Base):
    __tablename__ = "crm_activities"
    id = Column(String, primary_key=True, default=generate_uuid)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    activity_type = Column(String, nullable=False)
    description = Column(String, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
