import hashlib
import logging
import time
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


# ─── Schema definition: all tables and their expected columns ───
# Structure: { table_name: [(column_name, postgres_type, sqlite_type), ...] }
TABLES_TO_MIGRATE = {
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
        ('raw_queries', 'JSONB', 'JSON'),
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


def _compute_schema_hash():
    """Compute a deterministic hash of the expected schema definition.
    If TABLES_TO_MIGRATE changes (new table, new column, type change),
    the hash will differ, forcing migration to re-run."""
    h = hashlib.sha256()
    for table_name in sorted(TABLES_TO_MIGRATE.keys()):
        h.update(table_name.encode())
        for col_name, pg_type, sqlite_type in TABLES_TO_MIGRATE[table_name]:
            h.update(f"{col_name}:{pg_type}:{sqlite_type}".encode())
    return h.hexdigest()[:16]


def _get_stored_schema_hash(conn, is_pg):
    """Read the stored schema hash from _migration_meta table, if it exists."""
    try:
        result = conn.execute(text(
            "SELECT value FROM _migration_meta WHERE key = 'schema_hash' LIMIT 1"
        ))
        row = result.fetchone()
        return row[0] if row else None
    except Exception:
        # On PostgreSQL, a failed query aborts the transaction.
        # We must rollback to allow subsequent queries on this connection.
        try:
            conn.rollback()
        except Exception:
            pass
        return None


def _store_schema_hash(conn, schema_hash, is_pg):
    """Create the _migration_meta table (if needed) and upsert the schema hash."""
    conn.execute(text(
        "CREATE TABLE IF NOT EXISTS _migration_meta (key VARCHAR(100) PRIMARY KEY, value VARCHAR(255))"
    ))
    if is_pg:
        conn.execute(text(
            "INSERT INTO _migration_meta (key, value) VALUES ('schema_hash', :hash) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
        ), {"hash": schema_hash})
    else:
        conn.execute(text(
            "INSERT OR REPLACE INTO _migration_meta (key, value) VALUES ('schema_hash', :hash)"
        ), {"hash": schema_hash})


def run_migration():
    """
    Inspects all tables in the database and safely adds any missing columns.
    
    Optimizations over the original implementation:
    1. Schema hash check — skips migration entirely if nothing changed
    2. Bulk reflection — gets all table names + columns in minimal round trips
    3. Single connection — all work done in one connection/transaction
    4. Batched ALTERs — all column additions in one transaction
    """
    start_time = time.time()
    logger.info("Starting database schema migration check...")
    
    dialect_name = engine.dialect.name
    is_pg = (dialect_name == 'postgresql')
    expected_hash = _compute_schema_hash()
    
    logger.info(f"Database dialect: {dialect_name} | Expected schema hash: {expected_hash}")

    # Use a SINGLE connection for everything to avoid NullPool overhead
    with engine.connect() as conn:
        # ── Targeted compatibility migration for pain_points.job_id ──
        try:
            inspector = inspect(conn)
            if 'pain_points' in inspector.get_table_names():
                cols = [c['name'].lower() for c in inspector.get_columns('pain_points')]
                if 'job_id' not in cols:
                    logger.info("Targeted migration: Adding missing column pain_points.job_id")
                    col_type = 'VARCHAR(255)' if is_pg else 'TEXT'
                    conn.execute(text(f"ALTER TABLE pain_points ADD COLUMN job_id {col_type}"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pain_points_job_id ON pain_points(job_id)"))
                    logger.info("pain_points.job_id exists")
        except Exception as e:
            logger.warning(f"Failed to check/add pain_points.job_id: {e}")
            try:
                conn.rollback()
            except Exception:
                pass

        # ── Step 1: Check if migration can be skipped ──
        stored_hash = _get_stored_schema_hash(conn, is_pg)
        if stored_hash == expected_hash:
            elapsed = time.time() - start_time
            logger.info(f"Schema up to date (hash={expected_hash}) — skipping migration. ({elapsed:.2f}s)")
            print(f"[LeadPilot AI Migration] Schema up to date — skipped. ({elapsed:.2f}s)")
            return
        
        logger.info(f"Schema hash mismatch (stored={stored_hash}, expected={expected_hash}). Running migration...")

        # ── Step 2: Bulk-reflect existing tables and columns ──
        inspector = inspect(conn)
        existing_tables = set(inspector.get_table_names())
        logger.info(f"Found {len(existing_tables)} existing tables in database.")
        
        # Pre-fetch columns for all tables that exist and need migration (bulk)
        table_columns_cache = {}
        for table_name in TABLES_TO_MIGRATE:
            if table_name in existing_tables:
                cols = inspector.get_columns(table_name)
                table_columns_cache[table_name] = {col['name'].lower() for col in cols}
        
        logger.info(f"Reflected columns for {len(table_columns_cache)} tables.")

        # ── Step 3: Compute and batch all ALTER TABLE statements ──
        alter_statements = []
        for table_name, columns_to_add in TABLES_TO_MIGRATE.items():
            if table_name not in existing_tables:
                logger.warning(f"Table '{table_name}' does not exist yet. Will be created by Base.metadata.create_all.")
                continue
            
            existing_cols = table_columns_cache.get(table_name, set())
            
            for col_name, pg_type, sqlite_type in columns_to_add:
                if col_name.lower() not in existing_cols:
                    col_type = pg_type if is_pg else sqlite_type
                    quoted_name = f'"{col_name}"'
                    
                    if is_pg:
                        stmt = f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {quoted_name} {col_type};"
                    else:
                        stmt = f"ALTER TABLE {table_name} ADD COLUMN {quoted_name} {col_type};"
                    
                    alter_statements.append((table_name, col_name, stmt))

        # ── Step 4: Execute all ALTERs in one transaction ──
        if alter_statements:
            logger.info(f"Adding {len(alter_statements)} missing columns...")
            # Group by table for readable logging
            from collections import defaultdict
            by_table = defaultdict(list)
            for table_name, col_name, stmt in alter_statements:
                by_table[table_name].append(col_name)
                conn.execute(text(stmt))
            
            for table_name, cols in by_table.items():
                logger.info(f"  Added to '{table_name}': {', '.join(cols)}")
                print(f"[LeadPilot AI Migration] Added columns to '{table_name}': {', '.join(cols)}")
        else:
            logger.info("All columns already exist. No ALTER TABLE needed.")

        # ── Step 5: Store the schema hash so next startup is instant ──
        _store_schema_hash(conn, expected_hash, is_pg)
        conn.commit()

    elapsed = time.time() - start_time
    logger.info(f"Database schema migration check completed successfully. ({elapsed:.2f}s)")
    print(f"[LeadPilot AI Migration] All database tables synchronized! ({elapsed:.2f}s)\n")


def run_safe_migrations(engine_arg=None):
    """Alias for run_migration to support alternate startup invocations."""
    run_migration()

if __name__ == "__main__":
    run_migration()
