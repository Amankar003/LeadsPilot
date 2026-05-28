import streamlit as st
import pandas as pd
import threading
import os
import time
from utils.logging_utils import get_logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from config.database import SessionLocal
from modules.database.db_init import init_db
from modules.database.repositories import CampaignRepository, JobRepository, LeadRepository
from modules.input.manual_input import parse_manual_input
from modules.input.excel_parser import parse_excel_input
from modules.jobs.job_manager import JobManager
from modules.jobs.scraping_planner import ScrapingPlanner
from utils.constants import PLATFORM_GOOGLE_MAPS, PLATFORM_GOOGLE_EMAIL
from modules.ui.theme import inject_custom_css, page_header, empty_state, status_badge, workflow_indicator
from modules.ui.mailforge import render_mailforge

logger = get_logger(__name__)

# ─── Page Config ───
st.set_page_config(
    page_title="LeadPilot AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Database ───
@st.cache_resource
def setup_database():
    init_db()
setup_database()


def run_startup_checks():
    issues = []
    optional = []
    if not os.getenv("DATABASE_URL"):
        optional.append("DATABASE_URL not set, using local SQLite.")
    if not os.getenv("SERPER_API_KEY"):
        optional.append("SERPER_API_KEY missing: Serper features will be limited.")
    if not os.getenv("GROQ_API_KEY"):
        optional.append("No Groq API key configured. Fallback generation only.")
    for item in issues:
        st.error(item)
    for item in optional:
        st.warning(item)


run_startup_checks()


def launch_job(target, *args):
    """
    Run jobs in background for local mode, inline for worker mode.
    Set LEADPILOT_WORKER_MODE=true when using external workers.
    """
    if os.getenv("LEADPILOT_WORKER_MODE", "false").lower() == "true":
        target(*args)
        return None
    thread = threading.Thread(target=target, args=args, daemon=True)
    thread.start()
    return thread

# Start background worker thread safely
from modules.jobs.worker import BackgroundWorker
@st.cache_resource
def start_worker():
    worker = BackgroundWorker()
    worker.start()
    return worker
start_worker()

# Ensure analysis queue processor is running and recover any stuck jobs on startup
try:
    from modules.analysis.job_processor import recover_stuck_jobs, start_processor_thread
    try:
        recover_stuck_jobs()
    except Exception:
        logger.exception("Error while recovering stuck analysis jobs on startup")
    start_processor_thread()
except Exception:
    logger.warning("Analysis job processor not available at startup")


# ─── Theme ───
inject_custom_css()


def _get_query_params():
    """Return query params in a robust way across Streamlit versions.
    Tries `st.experimental_get_query_params()` then falls back to `st.query_params`.
    Returns a dict-like mapping (keys -> list-of-values or values).
    """
    try:
        return st.experimental_get_query_params()
    except Exception:
        try:
            qp = getattr(st, "query_params", {})
            if qp is None:
                return {}
            try:
                return dict(qp)
            except Exception:
                return qp
        except Exception:
            return {}

# ─── Sidebar ───
# If a `?page=...` query param is present, set the sidebar radio's session state
# so the deep link pre-selects the desired page.
try:
    qp = _get_query_params().get("page")
    if qp:
        qp_val = qp[0] if isinstance(qp, (list, tuple)) else qp
        if qp_val:
            st.session_state["Navigation"] = str(qp_val)
except Exception:
    pass

    
with st.sidebar:
    st.markdown("## 🚀 LeadPilot AI")
    st.caption("AI-Powered Lead Generation & Outreach")
    st.divider()

    st.markdown("##### 📋 DATA")
    page = st.radio(
        "Navigation",
        [
            "Dashboard",
            "Dork Optimizer",
            "Campaigns",
            "Lead Sources",
            "Lead Enrichment",
            "Lead Intelligence",
            "CRM",
            "MailForge",
            "Settings",
        ],
        label_visibility="collapsed",
    )

    st.divider()
    st.caption("v2.0 • LeadPilot AI")


# Clean page name (remove emoji prefix)
# Prefer explicit session state `Navigation` when present so the sidebar selection
# and routing stay consistent across runs and deep-links.
page = st.session_state.get("Navigation", page)
page_clean = page.strip()

# Allow overriding the selected page via URL query param `?page=...` (useful for deep links/testing)
try:
    params = _get_query_params()
    qp = params.get("page")
    if qp:
        qp_val = qp[0] if isinstance(qp, (list, tuple)) else qp
        if qp_val:
            page = str(qp_val)
            page_clean = page.strip()
except Exception:
    pass

# Direct deep-link handler: if URL requests the intelligence page, render it immediately
try:
    params = _get_query_params()
    qp = params.get("page")
    if qp:
        qp_val = qp[0] if isinstance(qp, (list, tuple)) else qp
        if qp_val and qp_val.strip() in ("Lead Intelligence", "AI Business Audit", "Lead Intelligence Report Engine"):
            from modules.ui.intelligence_ui import render_analysis_dashboard
            from modules.ui.report_viewer_ui import render_report_viewer
            audit_tab, report_tab = st.tabs(["Analysis Queue", "Reports"])
            with audit_tab:
                render_analysis_dashboard()
            with report_tab:
                render_report_viewer()
            st.stop()
except Exception:
    pass


# Skip separator items
if page_clean.startswith("──"):
    page = "Dashboard"
    page_clean = page.strip()


# ═══════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════
if page_clean == "Dashboard":
    page_header("📊", "Dashboard", "Real-time overview of your lead generation pipeline")

    db = SessionLocal()
    try:
        campaigns = CampaignRepository(db).get_all()
        jobs = JobRepository(db).get_all()
        leads = LeadRepository(db).get_all()

        from modules.database.models import LeadInsight, MailForgeDraft, MailForgeEmailLog

        # Row 1 — Core metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📋 Campaigns", len(campaigns))
        c2.metric("⚙️ Jobs", len(jobs))
        c3.metric("👥 Leads", len(leads))
        c4.metric("🔍 Scraped", sum(j.total_scraped for j in jobs) if jobs else 0)

        # Row 2 — AI & Outreach metrics
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("🧠 AI Analyzed", db.query(LeadInsight).count())
        c6.metric("✉️ Drafts", db.query(MailForgeDraft).count())
        c7.metric("📤 Sent", db.query(MailForgeEmailLog).filter(MailForgeEmailLog.status == "sent").count())
        c8.metric("🔥 Hot Leads", db.query(LeadInsight).filter(LeadInsight.lead_type == "HOT").count())

        # Workflow indicator
        st.divider()
        st.markdown("##### Pipeline Workflow")
        workflow_indicator(
            ["Scrape", "Clean", "AI Analyze", "Generate Email", "Review Draft", "Send", "Follow-up", "CRM"],
            active_index=-1
        )

        # Recent campaigns table
        if campaigns:
            st.divider()
            st.markdown("##### Recent Campaigns")
            camp_data = []
            for c in campaigns[:5]:
                camp_data.append({
                    "Campaign": c.campaign_name,
                    "Category": c.category,
                    "Location": c.location,
                    "Limit": c.limit,
                    "Status": c.status,
                    "Created": str(c.created_at)[:16],
                })
            st.dataframe(pd.DataFrame(camp_data), hide_index=True, width="stretch")

        # Recent jobs status
        if jobs:
            st.markdown("##### Recent Jobs")
            job_data = []
            for j in jobs[:5]:
                job_data.append({
                    "Platform": j.platform,
                    "Category": j.category,
                    "Location": j.location,
                    "Scraped": j.total_scraped,
                    "Saved": j.total_saved,
                    "Status": j.status,
                })
            st.dataframe(pd.DataFrame(job_data), hide_index=True, width="stretch")

    finally:
        db.close()


# ═══════════════════════════════════════════════
#  CREATE CAMPAIGN
# ═══════════════════════════════════════════════
elif page_clean == "Campaigns":
    page_header("➕", "Create Campaign", "Set up a new lead scraping campaign")

    tab1, tab3, tab5 = st.tabs(["📍 Scrape via Google Maps", "📂 Scrape via Excel/CSV", "🚀 Bulk SERP Scraper (Serper.dev)"])

    with tab1:
        db = SessionLocal()
        running_maps_job = None
        last_maps_job = None
        try:
            from modules.database.models import ScrapingJob
            from utils.constants import PLATFORM_GOOGLE_MAPS, JOB_RUNNING, JOB_PENDING
            
            all_maps_jobs = db.query(ScrapingJob).filter(
                ScrapingJob.platform == PLATFORM_GOOGLE_MAPS
            ).order_by(ScrapingJob.created_at.desc()).all()
            
            if all_maps_jobs:
                last_maps_job = all_maps_jobs[0]
                if last_maps_job.status in [JOB_RUNNING, JOB_PENDING]:
                    running_maps_job = last_maps_job
        finally:
            db.close()

        if running_maps_job:
            st.warning(f"⚠️ A Google Maps job is currently running for campaign: **{running_maps_job.campaign_id}**")
            
            # Show live metrics
            c1, c2, c3 = st.columns(3)
            c1.metric("📦 Scraped", running_maps_job.total_scraped)
            c2.metric("💾 Saved", running_maps_job.total_saved)
            c3.metric("🔁 Duplicates", running_maps_job.total_duplicates)
            
            if st.button("🛑 Stop Maps Scraping", type="primary", use_container_width=True):
                db = SessionLocal()
                try:
                    from utils.constants import JOB_STOPPED
                    job = db.query(ScrapingJob).filter(ScrapingJob.id == running_maps_job.id).first()
                    if job:
                        job.status = JOB_STOPPED
                        db.commit()
                        st.success("Stopping signal sent! The scraper will stop after current operations.")
                        st.rerun()
                finally:
                    db.close()
            
            # Show extracted data so far
            db = SessionLocal()
            try:
                from modules.database.models import Lead
                recent_leads = db.query(Lead).filter(Lead.scraping_job_id == running_maps_job.id).order_by(Lead.created_at.desc()).limit(15).all()
                if recent_leads:
                    st.markdown("##### 📌 Latest Extracted Leads")
                    lead_data = [{"Business": l.business_name, "Phone": l.phone or "N/A", "Rating": l.rating or "N/A"} for l in recent_leads]
                    st.dataframe(pd.DataFrame(lead_data), hide_index=True, width="stretch")
            finally:
                db.close()
                
            import time
            time.sleep(3)
            st.rerun()
            
        else:
            with st.form("maps_campaign_form"):
                st.markdown("##### 📍 Google Maps Campaign")
                col1, col2 = st.columns(2)
                with col1:
                    campaign_name = st.text_input("Campaign Name", "Maps Outreach v1")
                    category = st.text_input("Business Category", "Salons")
                with col2:
                    location = st.text_input("Location", "Delhi")
                    limit = st.number_input("Lead Limit (0 for ALL)", min_value=0, max_value=5000, value=100)

                submitted = st.form_submit_button("🚀 Start Maps Scraping", type="primary", use_container_width=True)
                if submitted:
                    instruction = parse_manual_input(
                        campaign_name, PLATFORM_GOOGLE_MAPS, category, location, limit, ["business_name", "phone", "website", "email", "address"],
                        enable_fallback=False
                    )
                    db = SessionLocal()
                    try:
                        manager = JobManager(db)
                        campaign, job = manager.create_campaign_and_job(instruction)
                        
                        def run_maps_job(j_id):
                            thread_db = SessionLocal()
                            try:
                                from modules.jobs.scraping_planner import ScrapingPlanner
                                planner = ScrapingPlanner(thread_db)
                                planner.execute_job(j_id)
                            finally:
                                thread_db.close()
                        
                        launch_job(run_maps_job, job.id)
                        
                        st.success(f"✅ Maps Campaign **{campaign.campaign_name}** created and started!")
                        st.balloons()
                        import time
                        time.sleep(1)
                        st.rerun()
                    finally:
                        db.close()
                        
            if last_maps_job and last_maps_job.status in ["COMPLETED", "STOPPED", "FAILED"]:
                st.divider()
                st.success(f"Previous scraping job ({last_maps_job.status}). Total Saved: {last_maps_job.total_saved}")
                db = SessionLocal()
                try:
                    from modules.database.models import Lead
                    extracted_leads = db.query(Lead).filter(Lead.scraping_job_id == last_maps_job.id).order_by(Lead.created_at.desc()).all()
                    if extracted_leads:
                        st.markdown("##### 📊 Extracted Data")
                        lead_data = []
                        for l in extracted_leads:
                            raw = l.raw_data or {}
                            lead_data.append({
                                "Business Name": l.business_name,
                                "Email": l.email or "",
                                "Phone": l.phone or "",
                                "Address": l.address or "",
                                "Website": l.website or "",
                                "Rating": l.rating or ""
                            })
                        st.dataframe(pd.DataFrame(lead_data), hide_index=True, width="stretch")
                finally:
                    db.close()



    with tab3:
        st.markdown("##### 📂 Direct Upload Leads via Excel/CSV")
        st.info("Upload your existing leads. Required columns (or variations): Name/Business, Email, Phone, Website.")
        
        campaign_name = st.text_input("Campaign Name for Upload", "Imported Leads")
        uploaded_file = st.file_uploader("Choose CSV/Excel File", type=['csv', 'xlsx', 'xls'])
        
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                
                st.write(f"Preview (Total rows: {len(df)}):")
                st.dataframe(df.head())
                
                if st.button("🚀 Import Leads", type="primary"):
                    db = SessionLocal()
                    try:
                        from modules.input.direct_importer import import_dataframe_to_leads
                        added_count, dup_count = import_dataframe_to_leads(db, df, campaign_name)
                        st.success(f"✅ Imported {added_count} new leads! (Skipped {dup_count} duplicates)")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Error importing leads: {str(e)}")
                    finally:
                        db.close()
            except Exception as e:
                st.error(f"Failed to read file: {e}")

    with tab5:
        st.markdown("##### 🚀 Serper.dev Bulk SERP Scraper")
        st.info("💡 **500+ leads** from one query are achieved by automatic query expansion and multiple SERP pages. Actual results depend on API quota and available websites.")
        
        with st.form("serper_bulk_form"):
            col1, col2 = st.columns(2)
            with col1:
                campaign_name = st.text_input("Campaign Name", "Serper Bulk v1")
                main_query = st.text_input("Main Query (e.g. Dentists)", "Dentists")
            with col2:
                location = st.text_input("Location (e.g. Noida)", "Noida")
                max_vars = st.number_input("Max Query Variations", min_value=1, max_value=200, value=50)
                max_pages = st.number_input("Max Pages Per Query", min_value=1, max_value=20, value=10)
            
            if not location:
                st.warning("⚠️ **For bulk SERP scraping, please add a location** like Noida, Delhi, Gurgaon, etc. Broad queries may return irrelevant global websites (e.g. Wikipedia, Mayo Clinic).")

            if "facebook.com" in main_query.lower():
                st.info("ℹ️ **Facebook Note:** Facebook pages cannot be scraped for contact info directly. The system will save the SERP results only. For direct email/phone leads, try queries like: 'carpenters in London official website'.")
            
            scrape_sites = st.checkbox("🔍 Scrape websites for emails/phones", value=True)
            
            submitted = st.form_submit_button("🚀 Start Bulk SERP Scraping", type="primary", use_container_width=True)
            
            if submitted:
                db = SessionLocal()
                try:
                    from modules.input.manual_input import parse_manual_input
                    from utils.constants import PLATFORM_SERPER_BULK
                    
                    instruction = parse_manual_input(
                        campaign_name, PLATFORM_SERPER_BULK, main_query, location, 10000, ["email", "phone", "website"],
                        enable_fallback=False
                    )
                    
                    manager = JobManager(db)
                    campaign, job = manager.create_campaign_and_job(instruction)
                    
                    def run_serper_bulk(j_id):
                        thread_db = SessionLocal()
                        try:
                            from modules.jobs.scraping_planner import ScrapingPlanner
                            planner = ScrapingPlanner(thread_db)
                            planner.execute_job(j_id)
                        finally:
                            thread_db.close()
                    
                    launch_job(run_serper_bulk, job.id)
                    
                    st.success(f"✅ Bulk Scraping Campaign **{campaign.campaign_name}** started!")
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
                finally:
                    db.close()

        # Show status of most recent Serper Bulk job
        db = SessionLocal()
        try:
            from modules.database.models import ScrapingJob
            from utils.constants import PLATFORM_SERPER_BULK, JOB_RUNNING, JOB_PENDING, JOB_STOPPED
            last_bulk_job = db.query(ScrapingJob).filter(ScrapingJob.platform == PLATFORM_SERPER_BULK).order_by(ScrapingJob.created_at.desc()).first()
            if last_bulk_job:
                st.divider()
                st.markdown(f"##### 📊 Current Bulk Job Status: **{last_bulk_job.status}**")
                c1, c2, c3 = st.columns(3)
                c1.metric("📦 Scraped", last_bulk_job.total_scraped)
                c2.metric("💾 Saved", last_bulk_job.total_saved)
                c3.metric("🔁 Duplicates", last_bulk_job.total_duplicates)
                
                if last_bulk_job.status in (JOB_RUNNING, JOB_PENDING):
                    if st.button("🛑 Stop Bulk Scraping", type="primary", use_container_width=True):
                        job = db.query(ScrapingJob).filter(ScrapingJob.id == last_bulk_job.id).first()
                        if job:
                            job.status = JOB_STOPPED
                            db.commit()
                            st.success("Stopping signal sent!")
                            st.rerun()
                    
                    if st.button("🔄 Refresh Status", use_container_width=True):
                        st.rerun()
                    st.info("Job is running in the background. It will collect ALL leads available.")
        finally:
            db.close()


# ═══════════════════════════════════════════════
#  SCRAPING JOBS
# ═══════════════════════════════════════════════
elif page_clean == "Lead Sources":
    page_header("⚙️", "Scraping Jobs", "Monitor and control your scraping jobs")

    db = SessionLocal()
    try:
        jobs = JobRepository(db).get_all()

        if not jobs:
            empty_state("🔍", "No Scraping Jobs", "Create a campaign first, then start the scraping job.")
        else:
            for job in jobs:
                # Status icon
                icon = {"PENDING": "⏳", "RUNNING": "🔄", "COMPLETED": "✅", "FAILED": "❌"}.get(job.status, "❓")
                with st.expander(f"{icon} {job.category} in {job.location} — **{job.status}**", expanded=(job.status == "RUNNING")):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("📦 Scraped", job.total_scraped)
                    c2.metric("💾 Saved", job.total_saved)
                    c3.metric("🔁 Duplicates", job.total_duplicates)
                    c4.metric("❌ Failed", job.total_failed)

                    st.caption(f"Job ID: `{job.id}` • Campaign: `{job.campaign_id[:8]}…` • Platform: {job.platform}")

                    if job.status in ("PENDING", "FAILED"):
                        if st.button("▶️ Start Job", key=f"start_{job.id}", type="primary"):
                            st.info("Job started in background…")
                            def run_job(j_id):
                                thread_db = SessionLocal()
                                try:
                                    planner = ScrapingPlanner(thread_db)
                                    planner.execute_job(j_id)
                                finally:
                                    thread_db.close()
                            launch_job(run_job, job.id)
                            st.rerun()

                    if job.status in ("RUNNING", "PENDING"):
                        if st.button("🛑 Stop Job", key=f"stop_{job.id}", type="primary"):
                            job.status = "STOPPED"
                            db.commit()
                            st.success("Stopping signal sent!")
                            st.rerun()

                    # Part 2: Campaign-wise Leads View/Download
                    col_view, col_dl, _ = st.columns([1, 1, 2])
                    
                    with col_view:
                        if st.button("👀 View Leads", key=f"view_{job.id}"):
                            st.session_state["view_job_id"] = job.id
                            
                    with col_dl:
                        from modules.database.models import Lead
                        leads = db.query(Lead).filter(Lead.scraping_job_id == job.id).all()
                        if leads:
                            df = pd.DataFrame([{
                                "Business Name": l.business_name,
                                "Email": l.email,
                                "Phone": l.phone,
                                "Website": l.website,
                                "Category": l.category,
                                "Status": l.status
                            } for l in leads])
                            csv = df.to_csv(index=False).encode('utf-8')
                            st.download_button("📥 Download (CSV)", data=csv, file_name=f"leads_{job.id}.csv", mime="text/csv", key=f"dl_{job.id}")

                    if st.session_state.get("view_job_id") == job.id:
                        from modules.database.models import Lead
                        job_leads = db.query(Lead).filter(Lead.scraping_job_id == job.id).all()
                        if job_leads:
                            lead_data = [{"Business": l.business_name, "Email": l.email, "Phone": l.phone, "Website": l.website} for l in job_leads]
                            st.dataframe(pd.DataFrame(lead_data), hide_index=True, width="stretch")
                            if st.button("Close View", key=f"close_{job.id}"):
                                st.session_state["view_job_id"] = None
                                st.rerun()
                        else:
                            st.info("No leads found for this job yet.")
    finally:
        db.close()


# ═══════════════════════════════════════════════
#  DORK OPTIMIZER
# ═══════════════════════════════════════════════
elif page_clean == "Dork Optimizer":
    from modules.ui.dork_optimizer_ui import render_dork_optimizer
    render_dork_optimizer()


# ═══════════════════════════════════════════════
#  LEADS
# ═══════════════════════════════════════════════
elif page_clean == "Lead Enrichment":
    page_header("🗂️", "Lead Database", "Browse, filter, and export your scraped leads")

    db = SessionLocal()
    try:
        leads = LeadRepository(db).get_all()

        if not leads:
            empty_state("👥", "No Leads Yet", "Run a scraping job to populate your lead database.")
        else:
            # Filters
            st.markdown("##### Filters")
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                filter_email = st.checkbox("📧 Has Email only")
            with fc2:
                filter_phone = st.checkbox("📞 Has Phone only")
            with fc3:
                filter_website = st.checkbox("🌐 Has Website only")

            data = []
            for l in leads:
                raw = l.raw_data or {}
                data.append({
                    "Select": True,
                    "Lead ID": l.id,
                    "Name/Business": l.business_name,
                    "Email": l.email or "",
                    "Phone": l.phone or "",
                    "Website": l.website or "",
                    "Category": l.category,
                    "Page": raw.get("page", ""),
                    "Result URL": raw.get("link", l.website or l.google_maps_url or ""),
                    "Created On": l.created_at.strftime("%Y-%m-%d %H:%M") if l.created_at else "",
                    "Status": l.status,
                })

            df = pd.DataFrame(data)
            if filter_email:
                df = df[df['Email'] != ""]
            if filter_phone:
                df = df[df['Phone'] != ""]
            if filter_website:
                df = df[df['Website'] != ""]

            st.markdown(f"##### Showing {len(df)} leads")
            
            # Interactive data editor to select leads
            edited_df = st.data_editor(
                df,
                column_config={
                    "Select": st.column_config.CheckboxColumn(required=True),
                    "Lead ID": None  # Hide Lead ID column
                },
                disabled=["Name/Business", "Email", "Phone", "Website", "Category", "Page", "Result URL", "Created On", "Status"],
                hide_index=True,
                use_container_width=True
            )

            # Lead selection mapping to MailForge
            selected_leads = edited_df[edited_df["Select"]] if not edited_df.empty else pd.DataFrame()
            if not selected_leads.empty:
                st.divider()
                st.markdown("#### 🚀 Pipeline to MailForge Outreach")
                from modules.database.models import MailForgeCampaign
                mf_campaigns = db.query(MailForgeCampaign).order_by(MailForgeCampaign.created_at.desc()).all()
                if not mf_campaigns:
                    st.warning("⚠️ No MailForge outreach campaigns found! Please create one in MailForge settings tab first.")
                else:
                    camp_opts = {c.id: c.name for c in mf_campaigns}
                    selected_mf_camp = st.selectbox(
                        "Target MailForge Campaign",
                        options=list(camp_opts.keys()),
                        format_func=lambda x: camp_opts[x],
                        key="leads_mf_select"
                    )
                    
                    if st.button("👉 Send Selected Leads to MailForge", type="primary", use_container_width=True):
                        from modules.mailforge.service import MailForgeService
                        service = MailForgeService()
                        selected_lead_ids = selected_leads["Lead ID"].tolist()
                        added = service.send_leads_to_mailforge(selected_mf_camp, selected_lead_ids)
                        st.success(f"🎉 Successfully sent **{added}** leads to MailForge Outreach Campaign!")
                        st.balloons()

            # Export
            csv = df.drop(columns=["Select", "Lead ID"]).to_csv(index=False).encode('utf-8')

            st.download_button(
                "📥 Download CSV",
                data=csv,
                file_name='leads_export.csv',
                mime='text/csv',
                type="primary"
            )
    finally:
        db.close()


# ═══════════════════════════════════════════════
#  AI LEAD ANALYSIS / Lead Intelligence
# ═══════════════════════════════════════════════
# Backwards-compatible routing: accept multiple historical names
elif page_clean in ("Lead Intelligence", "AI Business Audit", "Lead Intelligence Report Engine"):
    from modules.ui.intelligence_ui import render_analysis_dashboard
    from modules.ui.report_viewer_ui import render_report_viewer
    audit_tab, report_tab = st.tabs(["Analysis Queue", "Reports"])
    with audit_tab:
        render_analysis_dashboard()
    with report_tab:
        render_report_viewer()

# ═══════════════════════════════════════════════
#  EMAIL GENERATOR
# ═══════════════════════════════════════════════
elif page_clean == "CRM":
    from modules.ui.crm_ui import render_crm
    render_crm()

elif page_clean == "MailForge":
    from modules.ui.mailforge import render_mailforge
    render_mailforge()

# ═══════════════════════════════════════════════
#  SETTINGS
# ═══════════════════════════════════════════════
elif page_clean == "Settings":
    from modules.ui.settings_ui import render_settings
    render_settings()
else:
    st.error(f"No route configured for page: {page_clean}")
