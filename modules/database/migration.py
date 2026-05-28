import logging
from sqlalchemy import inspect, text
from config.database import engine

logger = logging.getLogger("leadpilot.database.migration")
# Ensure logging is visible in the console
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

def run_migration():
    """
    Inspects all tables in the Supabase PostgreSQL / SQLite database and safely adds any missing columns.
    Uses IF NOT EXISTS / database inspection to ensure it can be run multiple times safely.
    Supports both PostgreSQL and SQLite.
    """
    logger.info("Starting database schema migration check...")
    
    inspector = inspect(engine)
    dialect_name = engine.dialect.name
    is_pg = (dialect_name == 'postgresql')
    
    logger.info(f"Database dialect detected: {dialect_name}")

    # Explicit maps of tables and columns to check/add: (table_name, columns_list)
    # columns_list structure: (column_name, postgres_type, sqlite_type)
    tables_to_migrate = {
        'users': [
            ('full_name', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('email', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('hashed_password', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('is_active', 'BOOLEAN DEFAULT TRUE', 'BOOLEAN DEFAULT 1'),
            ('setup_completed', 'BOOLEAN DEFAULT TRUE', 'BOOLEAN DEFAULT 1'),
            ('created_at', 'TIMESTAMP', 'DATETIME'),
            ('updated_at', 'TIMESTAMP', 'DATETIME'),
        ],
        'leads': [
            ('user_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('scraping_job_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('domain', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('enrichment_status', "VARCHAR(50) DEFAULT 'PENDING'", "VARCHAR(50) DEFAULT 'PENDING'"),
            ('enrichment_source', 'VARCHAR(100)', 'VARCHAR(100)'),
            ('enriched_at', 'TIMESTAMP', 'DATETIME'),
            ('social_links', 'JSONB', 'JSON'),
            ('about_text', 'TEXT', 'TEXT'),
            ('services', 'JSONB', 'JSON'),
            ('email_source', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('email_confidence', 'VARCHAR(50)', 'VARCHAR(50)'),
            ('google_maps_url', 'TEXT', 'TEXT'),
            ('rating', 'DOUBLE PRECISION', 'FLOAT'),
            ('reviews_count', 'INTEGER', 'INTEGER'),
            ('source', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('city', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('state', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('country', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('has_email', 'BOOLEAN DEFAULT FALSE', 'BOOLEAN DEFAULT 0'),
            ('has_phone', 'BOOLEAN DEFAULT FALSE', 'BOOLEAN DEFAULT 0'),
            ('has_website', 'BOOLEAN DEFAULT FALSE', 'BOOLEAN DEFAULT 0'),
            ('status', "VARCHAR(100) DEFAULT 'NEW_LEAD'", "VARCHAR(100) DEFAULT 'NEW_LEAD'"),
            ('raw_data', 'JSONB', 'JSON'),
            ('lead_hash', 'VARCHAR(255)', 'VARCHAR(255)'),
        ],
        'email_drafts': [
            ('user_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('preview_text', 'TEXT', 'TEXT'),
            ('identified_problem', 'TEXT', 'TEXT'),
            ('proposed_solution', 'TEXT', 'TEXT'),
            ('personalization_used', 'TEXT', 'TEXT'),
            ('confidence_score', 'VARCHAR(50)', 'VARCHAR(50)'),
            ('email_type', "VARCHAR(100) DEFAULT 'initial'", "VARCHAR(100) DEFAULT 'initial'"),
            ('status', "VARCHAR(100) DEFAULT 'DRAFT'", "VARCHAR(100) DEFAULT 'DRAFT'"),
            ('generated_by_model', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('approved_by_user', 'BOOLEAN DEFAULT FALSE', 'BOOLEAN DEFAULT 0'),
            ('approved_at', 'TIMESTAMP', 'DATETIME'),
        ],
        'campaigns': [
            ('user_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('platform', 'VARCHAR(50)', 'VARCHAR(50)'),
            ('category', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('location', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('limit', 'INTEGER', 'INTEGER'),
            ('required_fields', 'JSONB', 'JSON'),
            ('enable_fallback', 'BOOLEAN', 'BOOLEAN'),
            ('max_fallback_results', 'INTEGER', 'INTEGER'),
            ('max_fallback_pages', 'INTEGER', 'INTEGER'),
            ('status', "VARCHAR(50) DEFAULT 'PENDING'", "VARCHAR(50) DEFAULT 'PENDING'"),
            ('created_at', 'TIMESTAMP', 'DATETIME'),
            ('updated_at', 'TIMESTAMP', 'DATETIME'),
        ],
        'scraping_jobs': [
            ('campaign_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('platform', 'VARCHAR(100)', 'VARCHAR(100)'),
            ('category', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('location', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('limit', 'INTEGER', 'INTEGER'),
            ('status', "VARCHAR(100) DEFAULT 'PENDING'", "VARCHAR(100) DEFAULT 'PENDING'"),
            ('enable_fallback', 'BOOLEAN', 'BOOLEAN'),
            ('max_fallback_results', 'INTEGER', 'INTEGER'),
            ('max_fallback_pages', 'INTEGER', 'INTEGER'),
            ('total_loaded', 'INTEGER DEFAULT 0', 'INTEGER DEFAULT 0'),
            ('total_scraped', 'INTEGER DEFAULT 0', 'INTEGER DEFAULT 0'),
            ('total_saved', 'INTEGER DEFAULT 0', 'INTEGER DEFAULT 0'),
            ('total_duplicates', 'INTEGER DEFAULT 0', 'INTEGER DEFAULT 0'),
            ('total_skipped', 'INTEGER DEFAULT 0', 'INTEGER DEFAULT 0'),
            ('total_failed', 'INTEGER DEFAULT 0', 'INTEGER DEFAULT 0'),
            ('error_message', 'TEXT', 'TEXT'),
            ('started_at', 'TIMESTAMP', 'DATETIME'),
            ('completed_at', 'TIMESTAMP', 'DATETIME'),
            ('created_at', 'TIMESTAMP', 'DATETIME'),
            ('updated_at', 'TIMESTAMP', 'DATETIME'),
        ],
        'email_logs': [
            ('user_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('recipient_email', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('subject', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('body', 'TEXT', 'TEXT'),
            ('provider', "VARCHAR(100) DEFAULT 'smtp'", "VARCHAR(100) DEFAULT 'smtp'"),
            ('provider_message_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('status', "VARCHAR(100) DEFAULT 'READY'", "VARCHAR(100) DEFAULT 'READY'"),
            ('sent_at', 'TIMESTAMP', 'DATETIME'),
            ('error_message', 'TEXT', 'TEXT'),
        ],
        'sender_accounts': [
            ('user_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('email', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('sender_email', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('encrypted_password', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('smtp_username', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('smtp_password', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('smtp_password_env_key', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('sendgrid_api_key_env', 'VARCHAR(255)', 'VARCHAR(255)'), # DEPRECATED
            ('sender_name', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('smtp_host', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('smtp_port', 'INTEGER', 'INTEGER'),
            ('provider', 'VARCHAR(100)', 'VARCHAR(100)'),
            ('daily_limit', 'INTEGER DEFAULT 100', 'INTEGER DEFAULT 100'),
            ('hourly_limit', 'INTEGER DEFAULT 10', 'INTEGER DEFAULT 10'),
            ('sent_today', 'INTEGER DEFAULT 0', 'INTEGER DEFAULT 0'),
            ('sent_this_hour', 'INTEGER DEFAULT 0', 'INTEGER DEFAULT 0'),
            ('last_reset_date', 'TIMESTAMP', 'DATETIME'),
            ('is_active', 'BOOLEAN DEFAULT TRUE', 'BOOLEAN DEFAULT 1'),
            ('is_verified', 'BOOLEAN DEFAULT FALSE', 'BOOLEAN DEFAULT 0'),
            ('health_status', "VARCHAR(100) DEFAULT 'GOOD'", "VARCHAR(100) DEFAULT 'GOOD'"),
            ('created_at', 'TIMESTAMP', 'DATETIME'),
            ('updated_at', 'TIMESTAMP', 'DATETIME'),
        ],
        'market_recommendations': [
            ('user_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('trend_name', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('country', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('region', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('sector', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('recommended_service', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('keywords_json', 'JSONB', 'JSON'),
            ('dorks_json', 'JSONB', 'JSON'),
            ('why_this_region', 'TEXT', 'TEXT'),
            ('why_this_sector', 'TEXT', 'TEXT'),
            ('opportunity_score', 'INTEGER DEFAULT 0', 'INTEGER DEFAULT 0'),
            ('status', "VARCHAR(100) DEFAULT 'PENDING'", "VARCHAR(100) DEFAULT 'PENDING'"),
            ('created_at', 'TIMESTAMP', 'DATETIME'),
        ],
        'dork_history': [
            ('user_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('dork_text', 'TEXT', 'TEXT'),
            ('dork_hash', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('country', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('region', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('sector', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('used_at', 'TIMESTAMP', 'DATETIME'),
            ('status', "VARCHAR(100) DEFAULT 'pending'", "VARCHAR(100) DEFAULT 'pending'"),
        ],
        'crm_notes': [
            ('user_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('lead_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('note', 'TEXT', 'TEXT'),
            ('created_at', 'TIMESTAMP', 'DATETIME'),
        ],
        'crm_activities': [
            ('activity_type', 'VARCHAR(100)', 'VARCHAR(100)'),
            ('description', 'TEXT', 'TEXT'),
            ('metadata_json', 'JSONB', 'JSON'),
        ],
        'followups': [
            ('parent_email_log_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('followup_number', 'INTEGER DEFAULT 1', 'INTEGER DEFAULT 1'),
            ('subject', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('body', 'TEXT', 'TEXT'),
            ('scheduled_at', 'TIMESTAMP', 'DATETIME'),
            ('sent_at', 'TIMESTAMP', 'DATETIME'),
            ('status', "VARCHAR(100) DEFAULT 'PENDING'", "VARCHAR(100) DEFAULT 'PENDING'"),
        ],
        'raw_scraped_records': [
            ('platform', 'VARCHAR(100)', 'VARCHAR(100)'),
            ('business_name', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('website', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('result_url', 'TEXT', 'TEXT'),
            ('email', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('phone', 'VARCHAR(100)', 'VARCHAR(100)'),
            ('address', 'TEXT', 'TEXT'),
            ('category', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('page', 'VARCHAR(100)', 'VARCHAR(100)'),
            ('source', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('raw_data', 'JSONB', 'JSON'),
            ('status', 'VARCHAR(100)', 'VARCHAR(100)'),
            ('skip_reason', 'TEXT', 'TEXT'),
        ],
        'lead_insights': [
            ('recommended_service', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('reason', 'TEXT', 'TEXT'),
            ('pain_points', 'JSONB', 'JSON'),
            ('lead_score', 'INTEGER DEFAULT 0', 'INTEGER DEFAULT 0'),
            ('lead_type', 'VARCHAR(100)', 'VARCHAR(100)'),
            ('ai_model', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('ai_response', 'JSONB', 'JSON'),
        ],
        'analysis_jobs': [
            ('website_url', 'TEXT', 'TEXT'),
            ('status', "VARCHAR(100) DEFAULT 'PENDING'", "VARCHAR(100) DEFAULT 'PENDING'"),
            ('priority', 'INTEGER DEFAULT 1', 'INTEGER DEFAULT 1'),
            ('error_message', 'TEXT', 'TEXT'),
            ('started_at', 'TIMESTAMP', 'DATETIME'),
            ('completed_at', 'TIMESTAMP', 'DATETIME'),
        ],
        'analysis_reports': [
            ('website_url', 'TEXT', 'TEXT'),
            ('has_website', 'BOOLEAN DEFAULT FALSE', 'BOOLEAN DEFAULT 0'),
            ('overall_score', 'INTEGER DEFAULT 0', 'INTEGER DEFAULT 0'),
            ('opportunity_score', 'INTEGER DEFAULT 0', 'INTEGER DEFAULT 0'),
            ('opportunity_level', 'VARCHAR(100)', 'VARCHAR(100)'),
            ('raw_audit_json', 'JSONB', 'JSON'),
            ('pain_points_json', 'JSONB', 'JSON'),
            ('recommended_services_json', 'JSONB', 'JSON'),
            ('ai_report_json', 'JSONB', 'JSON'),
        ],
        'pain_points': [
            ('type', 'VARCHAR(100)', 'VARCHAR(100)'),
            ('severity', 'VARCHAR(100)', 'VARCHAR(100)'),
            ('title', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('description', 'TEXT', 'TEXT'),
            ('evidence', 'TEXT', 'TEXT'),
            ('business_impact', 'TEXT', 'TEXT'),
            ('recommended_service', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('job_id', 'VARCHAR(255)', 'VARCHAR(255)'),
        ],
        'recommended_services': [
            ('service_name', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('priority', 'VARCHAR(100)', 'VARCHAR(100)'),
            ('reason', 'TEXT', 'TEXT'),
            ('pitch_angle', 'TEXT', 'TEXT'),
            ('job_id', 'VARCHAR(255)', 'VARCHAR(255)'),
        ],
        'outreach_messages': [
            ('email_type', 'VARCHAR(100)', 'VARCHAR(100)'),
            ('tone', 'VARCHAR(100)', 'VARCHAR(100)'),
            ('length', 'VARCHAR(100)', 'VARCHAR(100)'),
            ('cta_goal', 'VARCHAR(100)', 'VARCHAR(100)'),
            ('service_focus', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('subject_lines', 'JSONB', 'JSON'),
            ('email_body', 'TEXT', 'TEXT'),
            ('whatsapp_message', 'TEXT', 'TEXT'),
            ('linkedin_message', 'TEXT', 'TEXT'),
            ('follow_up_1', 'TEXT', 'TEXT'),
            ('follow_up_2', 'TEXT', 'TEXT'),
            ('is_approved', 'BOOLEAN DEFAULT FALSE', 'BOOLEAN DEFAULT 0'),
            ('approved_at', 'TIMESTAMP', 'DATETIME'),
            ('approved_subject', 'VARCHAR(255)', 'VARCHAR(255)'),
        ],
        'suppression_list': [
            ('email', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('reason', 'VARCHAR(255)', 'VARCHAR(255)'),
        ],
        'mailforge_campaigns': [
            ('name', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('description', 'TEXT', 'TEXT'),
            ('campaign_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('goal', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('tone', 'VARCHAR(100)', 'VARCHAR(100)'),
            ('email_length', 'VARCHAR(100)', 'VARCHAR(100)'),
            ('target_service', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('sender_profile', 'JSONB', 'JSON'),
            ('status', "VARCHAR(100) DEFAULT 'draft'", "VARCHAR(100) DEFAULT 'draft'"),
            ('created_at', 'TIMESTAMP', 'DATETIME'),
            ('updated_at', 'TIMESTAMP', 'DATETIME'),
        ],
        'mailforge_leads': [
            ('mailforge_campaign_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('lead_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('email', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('business_name', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('website', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('domain', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('enrichment_status', "VARCHAR(100) DEFAULT 'partial'", "VARCHAR(100) DEFAULT 'partial'"),
            ('confidence_score', 'VARCHAR(50)', 'VARCHAR(50)'),
            ('status', "VARCHAR(100) DEFAULT 'active'", "VARCHAR(100) DEFAULT 'active'"),
            ('created_at', 'TIMESTAMP', 'DATETIME'),
            ('updated_at', 'TIMESTAMP', 'DATETIME'),
        ],
        'mailforge_drafts': [
            ('mailforge_campaign_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('lead_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('subject', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('body', 'TEXT', 'TEXT'),
            ('opening_line', 'TEXT', 'TEXT'),
            ('cta', 'TEXT', 'TEXT'),
            ('personalization_reason', 'TEXT', 'TEXT'),
            ('confidence_score', 'VARCHAR(50)', 'VARCHAR(50)'),
            ('status', "VARCHAR(100) DEFAULT 'draft'", "VARCHAR(100) DEFAULT 'draft'"),
            ('version', 'INTEGER DEFAULT 1', 'INTEGER DEFAULT 1'),
            ('created_at', 'TIMESTAMP', 'DATETIME'),
            ('updated_at', 'TIMESTAMP', 'DATETIME'),
        ],
        'mailforge_followups': [
            ('mailforge_campaign_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('lead_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('parent_draft_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('followup_number', 'INTEGER DEFAULT 1', 'INTEGER DEFAULT 1'),
            ('subject', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('body', 'TEXT', 'TEXT'),
            ('scheduled_after_days', 'INTEGER DEFAULT 3', 'INTEGER DEFAULT 3'),
            ('status', "VARCHAR(100) DEFAULT 'pending'", "VARCHAR(100) DEFAULT 'pending'"),
            ('created_at', 'TIMESTAMP', 'DATETIME'),
            ('updated_at', 'TIMESTAMP', 'DATETIME'),
            ('sent_at', 'TIMESTAMP', 'DATETIME'),
        ],
        'mailforge_email_logs': [
            ('mailforge_campaign_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('lead_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('draft_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('sender_account_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('recipient_email', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('subject', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('body', 'TEXT', 'TEXT'),
            ('provider', 'VARCHAR(100)', 'VARCHAR(100)'),
            ('status', "VARCHAR(100) DEFAULT 'pending'", "VARCHAR(100) DEFAULT 'pending'"),
            ('error_message', 'TEXT', 'TEXT'),
            ('sent_at', 'TIMESTAMP', 'DATETIME'),
            ('created_at', 'TIMESTAMP', 'DATETIME'),
        ],
        'mailforge_suppression_list': [
            ('email', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('domain', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('reason', 'VARCHAR(100)', 'VARCHAR(100)'),
            ('source', 'VARCHAR(100)', 'VARCHAR(100)'),
            ('notes', 'TEXT', 'TEXT'),
            ('created_at', 'TIMESTAMP', 'DATETIME'),
        ],
        'dork_pipeline_runs': [
            ('run_type', "VARCHAR(100) DEFAULT 'auto'", "VARCHAR(100) DEFAULT 'auto'"),
            ('scope', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('country', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('state', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('region', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('category', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('target_service', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('status', "VARCHAR(100) DEFAULT 'completed'", "VARCHAR(100) DEFAULT 'completed'"),
            ('raw_config', 'JSONB', 'JSON'),
            ('created_at', 'TIMESTAMP', 'DATETIME'),
            ('completed_at', 'TIMESTAMP', 'DATETIME'),
        ],
        'dork_opportunities': [
            ('pipeline_run_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('country', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('state', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('region', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('category', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('target_service', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('trend_summary', 'TEXT', 'TEXT'),
            ('opportunity_reason', 'TEXT', 'TEXT'),
            ('suggested_offer', 'TEXT', 'TEXT'),
            ('score', 'INTEGER DEFAULT 0', 'INTEGER DEFAULT 0'),
            ('source_articles', 'JSONB', 'JSON'),
            ('created_at', 'TIMESTAMP', 'DATETIME'),
        ],
        'generated_dorks': [
            ('pipeline_run_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('opportunity_id', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('dork', 'TEXT', 'TEXT'),
            ('dork_type', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('quality_score', 'INTEGER DEFAULT 0', 'INTEGER DEFAULT 0'),
            ('intent', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('country', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('state', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('region', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('category', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('target_service', 'VARCHAR(255)', 'VARCHAR(255)'),
            ('status', "VARCHAR(100) DEFAULT 'draft'", "VARCHAR(100) DEFAULT 'draft'"),
            ('created_at', 'TIMESTAMP', 'DATETIME'),
        ],
    }

    # Run check for all tables
    for table_name, columns_to_add in tables_to_migrate.items():
        if not inspector.has_table(table_name):
            logger.warning(f"Table '{table_name}' does not exist yet. Creation will be handled by SQLAlchemy Base.metadata.create_all.")
            continue
            
        existing_cols = {col['name'].lower() for col in inspector.get_columns(table_name)}
        logger.info(f"Inspecting table '{table_name}'... (current columns count: {len(existing_cols)})")
        
        added_cols = []
        with engine.begin() as conn:
            for col_name, pg_type, sqlite_type in columns_to_add:
                if col_name.lower() not in existing_cols:
                    col_type = pg_type if is_pg else sqlite_type
                    # Quote column name to avoid reserved keyword conflicts
                    quoted_name = f'"{col_name}"'
                    
                    if is_pg:
                        query = f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {quoted_name} {col_type};"
                    else:
                        query = f"ALTER TABLE {table_name} ADD COLUMN {quoted_name} {col_type};"
                        
                    logger.info(f"Adding missing column to '{table_name}': {col_name} ({col_type})")
                    conn.execute(text(query))
                    added_cols.append(col_name)
                    
        if added_cols:
            logger.info(f"Successfully added missing columns to '{table_name}' table: {', '.join(added_cols)}")
            print(f"[LeadPilot AI Migration] Added columns to '{table_name}': {', '.join(added_cols)}")
        else:
            logger.debug(f"Table '{table_name}' schema is up to date.")

    logger.info("Database schema migration check completed successfully.")
    print("[LeadPilot AI Migration] All database tables are fully synchronized with SQLAlchemy models!\n")

def run_safe_migrations(engine_arg=None):
    """Alias for run_migration to support alternate startup invocations."""
    run_migration()

if __name__ == "__main__":
    run_migration()
