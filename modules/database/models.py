import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Boolean, Text, Float
from sqlalchemy.orm import relationship, validates
from config.database import Base

def generate_uuid():
    return str(uuid.uuid4())

def safe_int(value, default=0):
    if isinstance(value, tuple):
        value = value[0] if value else default
    try:
        return int(value)
    except Exception:
        return default

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    setup_completed = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
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

    @validates("limit", "max_fallback_results", "max_fallback_pages")
    def validate_numeric_fields(self, key, value):
        default_val = 100 if key == "limit" else (5 if key == "max_fallback_results" else 2)
        return safe_int(value, default=default_val)

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
    
    total_loaded = Column(Integer, default=0)
    total_scraped = Column(Integer, default=0)
    total_saved = Column(Integer, default=0)
    total_duplicates = Column(Integer, default=0)
    total_skipped = Column(Integer, default=0)
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
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    scraping_job_id = Column(String, ForeignKey("scraping_jobs.id"), nullable=False)
    
    business_name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    website = Column(String, nullable=True)
    domain = Column(String, nullable=True)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    country = Column(String, nullable=True)
    rating = Column(Float, nullable=True)
    reviews_count = Column(Integer, nullable=True)
    source = Column(String, nullable=True)
    google_maps_url = Column(String, nullable=True)
    email_source = Column(String, nullable=True)
    email_confidence = Column(String, nullable=True)
    # Enrichment metadata
    enrichment_status = Column(String, default="PENDING")
    enrichment_source = Column(String, nullable=True)
    enriched_at = Column(DateTime, nullable=True)
    social_links = Column(JSON, default=dict)
    about_text = Column(Text, nullable=True)
    services = Column(JSON, default=list)
    
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

    @validates("rating")
    def validate_rating(self, key, value):
        from utils.type_utils import safe_float
        return safe_float(value)

    @validates("reviews_count")
    def validate_reviews_count(self, key, value):
        from utils.type_utils import safe_int
        return safe_int(value)

class RawScrapedRecord(Base):
    __tablename__ = "raw_scraped_records"

    id = Column(String, primary_key=True, default=generate_uuid)
    job_id = Column(String, ForeignKey("scraping_jobs.id"), nullable=False)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    
    platform = Column(String, nullable=True)
    business_name = Column(String, nullable=True)
    website = Column(String, nullable=True)
    result_url = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    category = Column(String, nullable=True)
    page = Column(String, nullable=True)
    source = Column(String, nullable=True)
    
    raw_data = Column(JSON, default=dict)
    
    status = Column(String, nullable=False)
    skip_reason = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("ScrapingJob")
    campaign = relationship("Campaign")

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
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
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
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    email_draft_id = Column(String, ForeignKey("email_drafts.id"), nullable=True)
    recipient_email = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(String, nullable=False)
    provider = Column(String, default="smtp")  # Default changed from sendgrid to smtp
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

# ==========================================
# LEAD INTELLIGENCE / ANALYSIS TABLES
# ==========================================

class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    id = Column(String, primary_key=True, default=generate_uuid)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False)
    website_url = Column(String, nullable=True)
    status = Column(String, default="PENDING")  # PENDING, RUNNING, COMPLETED, FAILED
    priority = Column(Integer, default=1)
    error_message = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    lead = relationship("Lead")

class AnalysisReport(Base):
    __tablename__ = "analysis_reports"
    id = Column(String, primary_key=True, default=generate_uuid)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False)
    job_id = Column(String, ForeignKey("analysis_jobs.id"), nullable=False)
    
    website_url = Column(String, nullable=True)
    has_website = Column(Boolean, default=False)
    
    # Scores
    overall_score = Column(Integer, default=0)
    opportunity_score = Column(Integer, default=0)
    opportunity_level = Column(String, nullable=True)
    
    # Raw JSON Data
    raw_audit_json = Column(JSON, default=dict)
    pain_points_json = Column(JSON, default=list)
    recommended_services_json = Column(JSON, default=list)
    ai_report_json = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PainPoint(Base):
    __tablename__ = "pain_points"
    id = Column(String, primary_key=True, default=generate_uuid)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False)
    job_id = Column(String, ForeignKey("analysis_jobs.id"), nullable=False)
    
    type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    evidence = Column(String, nullable=True)
    business_impact = Column(String, nullable=True)
    recommended_service = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

class RecommendedService(Base):
    __tablename__ = "recommended_services"
    id = Column(String, primary_key=True, default=generate_uuid)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False)
    job_id = Column(String, ForeignKey("analysis_jobs.id"), nullable=False)
    
    service_name = Column(String, nullable=False)
    priority = Column(String, nullable=False)
    reason = Column(String, nullable=True)
    pitch_angle = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class OutreachMessage(Base):
    """Stores every AI-generated outreach variation for a lead."""
    __tablename__ = "outreach_messages"
    id = Column(String, primary_key=True, default=generate_uuid)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False)
    report_id = Column(String, ForeignKey("analysis_reports.id"), nullable=True)

    # Generation settings
    email_type = Column(String, nullable=True)
    tone = Column(String, nullable=True)
    length = Column(String, nullable=True)
    cta_goal = Column(String, nullable=True)
    service_focus = Column(String, nullable=True)

    # Generated content (JSON fields)
    subject_lines = Column(JSON, default=list)
    email_body = Column(String, nullable=True)
    whatsapp_message = Column(String, nullable=True)
    linkedin_message = Column(String, nullable=True)
    follow_up_1 = Column(String, nullable=True)
    follow_up_2 = Column(String, nullable=True)

    # Approval tracking
    is_approved = Column(Boolean, default=False)
    approved_at = Column(DateTime, nullable=True)
    approved_subject = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lead = relationship("Lead")


class Dork(Base):
    __tablename__ = "dorks"

    id = Column(String, primary_key=True, default=generate_uuid)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    dork_text = Column(String, nullable=False)
    source_file = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, scraped, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    campaign = relationship("Campaign")

class SenderAccount(Base):
    __tablename__ = "sender_accounts"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    email = Column(String, nullable=False)
    sender_email = Column(String, nullable=True)
    encrypted_password = Column(String, nullable=False)
    smtp_username = Column(String, nullable=True)
    smtp_password = Column(String, nullable=True)
    smtp_password_env_key = Column(String, nullable=True)
    sendgrid_api_key_env = Column(String, nullable=True)  # DEPRECATED: No longer used, kept for DB schema compatibility
    sender_name = Column(String, nullable=True)
    smtp_host = Column(String, nullable=True)
    smtp_port = Column(Integer, nullable=True)
    provider = Column(String, nullable=True)  # e.g., smtp, custom_smtp, gmail_smtp
    daily_limit = Column(Integer, default=100)
    hourly_limit = Column(Integer, default=10)
    sent_today = Column(Integer, default=0)
    sent_this_hour = Column(Integer, default=0)
    last_reset_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    health_status = Column(String, default="GOOD")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MailForgeCampaign(Base):
    __tablename__ = "mailforge_campaigns"
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=True)
    goal = Column(String, nullable=True)
    tone = Column(String, nullable=True)
    email_length = Column(String, nullable=True)
    target_service = Column(String, nullable=True)
    sender_profile = Column(JSON, default=dict)
    status = Column(String, default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MailForgeLead(Base):
    __tablename__ = "mailforge_leads"
    id = Column(String, primary_key=True, default=generate_uuid)
    mailforge_campaign_id = Column(String, ForeignKey("mailforge_campaigns.id"), nullable=False)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=True)
    email = Column(String, nullable=False, index=True)
    business_name = Column(String, nullable=True)
    website = Column(String, nullable=True)
    domain = Column(String, nullable=True)
    enrichment_status = Column(String, default="partial")
    confidence_score = Column(String, nullable=True)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MailForgeDraft(Base):
    __tablename__ = "mailforge_drafts"
    id = Column(String, primary_key=True, default=generate_uuid)
    mailforge_campaign_id = Column(String, ForeignKey("mailforge_campaigns.id"), nullable=False)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=True)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    opening_line = Column(String, nullable=True)
    cta = Column(String, nullable=True)
    personalization_reason = Column(Text, nullable=True)
    confidence_score = Column(String, nullable=True)
    status = Column(String, default="draft")
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MailForgeFollowUp(Base):
    __tablename__ = "mailforge_followups"
    id = Column(String, primary_key=True, default=generate_uuid)
    mailforge_campaign_id = Column(String, ForeignKey("mailforge_campaigns.id"), nullable=False)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=True)
    parent_draft_id = Column(String, ForeignKey("mailforge_drafts.id"), nullable=True)
    followup_number = Column(Integer, default=1)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    scheduled_after_days = Column(Integer, default=3)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)


class MailForgeEmailLog(Base):
    __tablename__ = "mailforge_email_logs"
    id = Column(String, primary_key=True, default=generate_uuid)
    mailforge_campaign_id = Column(String, ForeignKey("mailforge_campaigns.id"), nullable=False)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=True)
    draft_id = Column(String, ForeignKey("mailforge_drafts.id"), nullable=True)
    sender_account_id = Column(String, ForeignKey("sender_accounts.id"), nullable=True)
    recipient_email = Column(String, nullable=False, index=True)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    provider = Column(String, nullable=True)
    status = Column(String, default="pending")
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class MailForgeSuppressionList(Base):
    __tablename__ = "mailforge_suppression_list"
    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, nullable=False, unique=True, index=True)
    domain = Column(String, nullable=True)
    reason = Column(String, nullable=False)
    source = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class MailForgeSetting(Base):
    """Key-value settings table for MailForge bulk sending engine."""
    __tablename__ = "mailforge_settings"
    id = Column(String, primary_key=True, default=generate_uuid)
    key = Column(String, nullable=False, unique=True, index=True)
    value = Column(String, nullable=True)
    value_type = Column(String, default="string")  # string, int, float, bool
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MarketRecommendation(Base):
    __tablename__ = "market_recommendations"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    trend_name = Column(String, nullable=False)
    country = Column(String, nullable=True)
    region = Column(String, nullable=True)
    sector = Column(String, nullable=True)
    recommended_service = Column(String, nullable=True)
    keywords_json = Column(JSON, default=list)
    dorks_json = Column(JSON, default=list)
    why_this_region = Column(Text, nullable=True)
    why_this_sector = Column(Text, nullable=True)
    opportunity_score = Column(Integer, default=0)
    status = Column(String, default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)

class DorkHistory(Base):
    __tablename__ = "dork_history"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    dork_text = Column(Text, nullable=False)
    dork_hash = Column(String, nullable=True)
    country = Column(String, nullable=True)
    region = Column(String, nullable=True)
    sector = Column(String, nullable=True)
    used_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending")

class CRMNote(Base):
    __tablename__ = "crm_notes"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class DorkPipelineRun(Base):
    __tablename__ = "dork_pipeline_runs"

    id = Column(String, primary_key=True, default=generate_uuid)
    run_type = Column(String, default="auto")  # auto, manual
    scope = Column(String, nullable=False)     # global, country, category
    country = Column(String, nullable=True)
    state = Column(String, nullable=True)
    region = Column(String, nullable=True)
    category = Column(String, nullable=True)
    target_service = Column(String, nullable=True)
    status = Column(String, default="completed")
    raw_config = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    opportunities = relationship("DorkOpportunity", back_populates="pipeline_run", cascade="all, delete-orphan")
    dorks = relationship("GeneratedDork", back_populates="pipeline_run", cascade="all, delete-orphan")


class DorkOpportunity(Base):
    __tablename__ = "dork_opportunities"

    id = Column(String, primary_key=True, default=generate_uuid)
    pipeline_run_id = Column(String, ForeignKey("dork_pipeline_runs.id"), nullable=False)
    country = Column(String, nullable=True)
    state = Column(String, nullable=True)
    region = Column(String, nullable=True)
    category = Column(String, nullable=True)
    target_service = Column(String, nullable=True)
    trend_summary = Column(Text, nullable=True)
    opportunity_reason = Column(Text, nullable=True)
    suggested_offer = Column(Text, nullable=True)
    score = Column(Integer, default=0)
    source_articles = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    pipeline_run = relationship("DorkPipelineRun", back_populates="opportunities")
    dorks = relationship("GeneratedDork", back_populates="opportunity", cascade="all, delete-orphan")


class GeneratedDork(Base):
    __tablename__ = "generated_dorks"

    id = Column(String, primary_key=True, default=generate_uuid)
    pipeline_run_id = Column(String, ForeignKey("dork_pipeline_runs.id"), nullable=True)
    opportunity_id = Column(String, ForeignKey("dork_opportunities.id"), nullable=True)
    dork = Column(String, nullable=False)
    dork_type = Column(String, nullable=True)  # business_discovery, contact_page, email_discovery, phone_whatsapp, low_digital_presence, service_need
    quality_score = Column(Integer, default=0)
    intent = Column(String, nullable=True)
    country = Column(String, nullable=True)
    state = Column(String, nullable=True)
    region = Column(String, nullable=True)
    category = Column(String, nullable=True)
    target_service = Column(String, nullable=True)
    status = Column(String, default="draft")  # draft, saved, scraped
    created_at = Column(DateTime, default=datetime.utcnow)

    pipeline_run = relationship("DorkPipelineRun", back_populates="dorks")
    opportunity = relationship("DorkOpportunity", back_populates="dorks")


def get_or_create_default_user(db):
    user = db.query(User).filter(User.id == "default-user").first()
    if user:
        return user

    user = User(
        id="default-user",
        full_name="Default User",
        email="default@leadpilot.local",
        hashed_password="not-used",
        is_active=True,
        setup_completed=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user



