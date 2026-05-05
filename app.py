import streamlit as st
import pandas as pd
import threading
import os
import time
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

# ─── Theme ───
inject_custom_css()

# ─── Sidebar ───
with st.sidebar:
    st.markdown("## 🚀 LeadPilot AI")
    st.caption("AI-Powered Lead Generation & Outreach")
    st.divider()

    st.markdown("##### 📋 DATA")
    page = st.radio(
        "Navigation",
        [
            "📊 Dashboard",
            "➕ Create Campaign",
            "⚙️ Scraping Jobs",
            "🗂️ Leads",
            "───────────────",
            "🧠 AI Lead Analysis",
            "✉️ Email Generator",
            "📝 Email Drafts",
            "───────────────",
            "📤 Send Emails",
            "📋 Email Logs",
            "🔁 Follow-ups",
            "───────────────",
            "📈 CRM Pipeline",
            "⚙️ Settings",
        ],
        label_visibility="collapsed",
    )

    st.divider()
    st.caption("v2.0 • LeadPilot AI")

# Clean page name (remove emoji prefix)
page_clean = page.strip()

# Skip separator items
if page_clean.startswith("──"):
    page = "📊 Dashboard"
    page_clean = page.strip()


# ═══════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════
if page_clean == "📊 Dashboard":
    page_header("📊", "Dashboard", "Real-time overview of your lead generation pipeline")

    db = SessionLocal()
    try:
        campaigns = CampaignRepository(db).get_all()
        jobs = JobRepository(db).get_all()
        leads = LeadRepository(db).get_all()

        from modules.database.models import LeadInsight, EmailDraft, EmailLog

        # Row 1 — Core metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📋 Campaigns", len(campaigns))
        c2.metric("⚙️ Jobs", len(jobs))
        c3.metric("👥 Leads", len(leads))
        c4.metric("🔍 Scraped", sum(j.total_scraped for j in jobs) if jobs else 0)

        # Row 2 — AI & Outreach metrics
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("🧠 AI Analyzed", db.query(LeadInsight).count())
        c6.metric("✉️ Drafts", db.query(EmailDraft).count())
        c7.metric("📤 Sent", db.query(EmailLog).filter(EmailLog.status == "SENT").count())
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
elif page_clean == "➕ Create Campaign":
    page_header("➕", "Create Campaign", "Set up a new lead scraping campaign")

    tab1, tab2, tab4, tab3, tab5 = st.tabs(["📍 Scrape via Google Maps", "🔍 Scrape via Google SERP", "🔍 Google SERP Search", "📂 Scrape via Excel/CSV", "🚀 Bulk SERP Scraper (Serper.dev)"])

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
                        
                        thread = threading.Thread(target=run_maps_job, args=(job.id,), daemon=True)
                        thread.start()
                        
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

    with tab2:
        db = SessionLocal()
        running_serp_job = None
        last_serp_job = None
        try:
            from modules.database.models import ScrapingJob
            from utils.constants import PLATFORM_GOOGLE_EMAIL, JOB_RUNNING, JOB_PENDING
            
            all_serp_jobs = db.query(ScrapingJob).filter(
                ScrapingJob.platform == PLATFORM_GOOGLE_EMAIL
            ).order_by(ScrapingJob.created_at.desc()).all()
            
            if all_serp_jobs:
                last_serp_job = all_serp_jobs[0]
                if last_serp_job.status in [JOB_RUNNING, JOB_PENDING]:
                    running_serp_job = last_serp_job
        finally:
            db.close()

        if running_serp_job:
            st.warning(f"⚠️ A Google SERP job is currently running for campaign: **{running_serp_job.campaign_id}**")
            
            # Show live metrics
            c1, c2, c3 = st.columns(3)
            c1.metric("📦 Scraped", running_serp_job.total_scraped)
            c2.metric("💾 Saved", running_serp_job.total_saved)
            c3.metric("🔁 Duplicates", running_serp_job.total_duplicates)
            
            if st.button("🛑 Stop Scraping", type="primary", use_container_width=True):
                db = SessionLocal()
                try:
                    from utils.constants import JOB_STOPPED
                    job = db.query(ScrapingJob).filter(ScrapingJob.id == running_serp_job.id).first()
                    if job:
                        job.status = JOB_STOPPED
                        db.commit()
                        st.success("Stopping signal sent! The scraper will stop after finishing the current page.")
                        st.rerun()
                finally:
                    db.close()
            
            # Show extracted data so far
            db = SessionLocal()
            try:
                from modules.database.models import Lead
                recent_leads = db.query(Lead).filter(Lead.scraping_job_id == running_serp_job.id).order_by(Lead.created_at.desc()).limit(15).all()
                if recent_leads:
                    st.markdown("##### 📌 Latest Extracted Leads")
                    lead_data = []
                    for l in recent_leads:
                        raw = l.raw_data or {}
                        lead_data.append({
                            "Business": l.business_name,
                            "Email": l.email or "N/A",
                            "Phone": l.phone or "N/A",
                            "Title": raw.get("result_title", ""),
                            "Page": raw.get("serp_page", "")
                        })
                    st.dataframe(pd.DataFrame(lead_data), hide_index=True, width="stretch")
            finally:
                db.close()
                
            import time
            time.sleep(3)
            st.rerun()
        
        else:
            with st.form("email_campaign_form"):
                st.markdown("##### 🔍 Google SERP Scraper")
                col1, col2 = st.columns(2)
                with col1:
                    campaign_name = st.text_input("Campaign Name", "Email Harvesting v1")
                    queries_text = st.text_area("Search Queries (One per line)", 
                                             '"London" Carpenters site:facebook.com\n"London" Plumbers site:facebook.com',
                                             help="Enter one search query per line. The scraper will process them sequentially.")
                with col2:
                    location = st.text_input("Location (optional)", "")

                st.info("💡 **Tip**: Use advanced operators like `site:facebook.com` or `\"@gmail.com\"` to target specific domains or providers.")

                submitted = st.form_submit_button("🚀 Start Scraping", type="primary", use_container_width=True)
                if submitted:
                    instruction = parse_manual_input(
                        campaign_name, PLATFORM_GOOGLE_EMAIL, queries_text, location, 0, ["email", "source_url"],
                        enable_fallback=False
                    )
                    db = SessionLocal()
                    try:
                        manager = JobManager(db)
                        campaign, job = manager.create_campaign_and_job(instruction)
                        
                        def run_job(j_id):
                            thread_db = SessionLocal()
                            try:
                                planner = ScrapingPlanner(thread_db)
                                planner.execute_job(j_id)
                            finally:
                                thread_db.close()
                        
                        thread = threading.Thread(target=run_job, args=(job.id,), daemon=True)
                        thread.start()
                        
                        st.success(f"✅ Email Campaign **{campaign.campaign_name}** created and started!")
                        st.balloons()
                        import time
                        time.sleep(1)
                        st.rerun()
                    finally:
                        db.close()
                        
            if last_serp_job and last_serp_job.status in ["COMPLETED", "STOPPED", "FAILED"]:
                st.divider()
                st.success(f"Previous scraping job ({last_serp_job.status}). Total Saved: {last_serp_job.total_saved}")
                db = SessionLocal()
                try:
                    from modules.database.models import Lead
                    extracted_leads = db.query(Lead).filter(Lead.scraping_job_id == last_serp_job.id).order_by(Lead.created_at.desc()).all()
                    if extracted_leads:
                        st.markdown("##### 📊 Extracted Data")
                        lead_data = []
                        for l in extracted_leads:
                            raw = l.raw_data or {}
                            lead_data.append({
                                "Business Name": l.business_name,
                                "Email": l.email or "",
                                "Phone": l.phone or "",
                                "Result Title": raw.get("result_title", ""),
                                "Result URL": raw.get("result_url", l.google_maps_url or ""),
                                "Page": raw.get("serp_page", ""),
                                "Date": raw.get("createdOn", l.created_at.strftime("%Y-%m-%d %H:%M") if l.created_at else "")
                            })
                        st.dataframe(pd.DataFrame(lead_data), hide_index=True, width="stretch")
                finally:
                    db.close()

    with tab4:
        db = SessionLocal()
        running_adv_job = None
        last_adv_job = None
        try:
            from modules.database.models import ScrapingJob
            from utils.constants import PLATFORM_GOOGLE_SERP, JOB_RUNNING, JOB_PENDING
            
            all_adv_jobs = db.query(ScrapingJob).filter(
                ScrapingJob.platform == PLATFORM_GOOGLE_SERP
            ).order_by(ScrapingJob.created_at.desc()).all()
            
            if all_adv_jobs:
                last_adv_job = all_adv_jobs[0]
                if last_adv_job.status in [JOB_RUNNING, JOB_PENDING]:
                    running_adv_job = last_adv_job
        finally:
            db.close()

        if running_adv_job:
            st.warning(f"⚠️ A Google SERP Search job is currently running for campaign: **{running_adv_job.campaign_id}**")
            
            # Show live metrics
            c1, c2, c3 = st.columns(3)
            c1.metric("📦 Scraped", running_adv_job.total_scraped)
            c2.metric("💾 Saved", running_adv_job.total_saved)
            c3.metric("🔁 Duplicates", running_adv_job.total_duplicates)
            
            if st.button("🛑 Stop Advanced Scraping", type="primary", use_container_width=True):
                db = SessionLocal()
                try:
                    from utils.constants import JOB_STOPPED
                    job = db.query(ScrapingJob).filter(ScrapingJob.id == running_adv_job.id).first()
                    if job:
                        job.status = JOB_STOPPED
                        db.commit()
                        st.success("Stopping signal sent! The scraper will stop after finishing the current page.")
                        st.rerun()
                finally:
                    db.close()
            
            # Show extracted data so far
            db = SessionLocal()
            try:
                from modules.database.models import Lead
                recent_leads = db.query(Lead).filter(Lead.scraping_job_id == running_adv_job.id).order_by(Lead.created_at.desc()).limit(15).all()
                if recent_leads:
                    st.markdown("##### 📌 Latest Extracted Leads")
                    lead_data = []
                    for l in recent_leads:
                        raw = l.raw_data or {}
                        lead_data.append({
                            "Business": l.business_name,
                            "Email": l.email or "N/A",
                            "Phone": l.phone or "N/A",
                            "Title": raw.get("result_title", ""),
                            "Page": raw.get("serp_page", "")
                        })
                    st.dataframe(pd.DataFrame(lead_data), hide_index=True, width="stretch")
            finally:
                db.close()
                
            import time
            time.sleep(3)
            st.rerun()
        
        else:
            with st.form("adv_campaign_form"):
                st.markdown("##### 🔍 Google SERP Search (Manager's Scraper)")
                col1, col2 = st.columns(2)
                with col1:
                    campaign_name = st.text_input("Campaign Name", "Advanced SERP Campaign v1")
                    queries_text = st.text_area("Search Queries (One per line)", 
                                             '"London" Carpenters site:facebook.com\n"London" Plumbers site:facebook.com',
                                             help="Enter one search query per line. The scraper will process them sequentially.", key="adv_queries_text")
                with col2:
                    location = st.text_input("Location (optional)", "", key="adv_location")

                submitted = st.form_submit_button("🚀 Start Advanced Scraping", type="primary", use_container_width=True)
                if submitted:
                    instruction = parse_manual_input(
                        campaign_name, PLATFORM_GOOGLE_SERP, queries_text, location, 0, ["email", "source_url"],
                        enable_fallback=False
                    )
                    db = SessionLocal()
                    try:
                        manager = JobManager(db)
                        campaign, job = manager.create_campaign_and_job(instruction)
                        
                        def run_adv_job(j_id):
                            thread_db = SessionLocal()
                            try:
                                planner = ScrapingPlanner(thread_db)
                                planner.execute_job(j_id)
                            finally:
                                thread_db.close()
                        
                        thread = threading.Thread(target=run_adv_job, args=(job.id,), daemon=True)
                        thread.start()
                        
                        st.success(f"✅ Advanced SERP Campaign **{campaign.campaign_name}** created and started!")
                        st.balloons()
                        import time
                        time.sleep(1)
                        st.rerun()
                    finally:
                        db.close()
                        
            if last_adv_job and last_adv_job.status in ["COMPLETED", "STOPPED", "FAILED"]:
                st.divider()
                st.success(f"Previous scraping job ({last_adv_job.status}). Total Saved: {last_adv_job.total_saved}")
                db = SessionLocal()
                try:
                    from modules.database.models import Lead
                    extracted_leads = db.query(Lead).filter(Lead.scraping_job_id == last_adv_job.id).order_by(Lead.created_at.desc()).all()
                    if extracted_leads:
                        st.markdown("##### 📊 Extracted Data")
                        lead_data = []
                        for l in extracted_leads:
                            raw = l.raw_data or {}
                            lead_data.append({
                                "Business Name": l.business_name,
                                "Email": l.email or "",
                                "Phone": l.phone or "",
                                "Result Title": raw.get("result_title", ""),
                                "Result URL": raw.get("result_url", l.google_maps_url or ""),
                                "Page": raw.get("serp_page", ""),
                                "Date": raw.get("createdOn", l.created_at.strftime("%Y-%m-%d %H:%M") if l.created_at else "")
                            })
                        st.dataframe(pd.DataFrame(lead_data), hide_index=True, width="stretch")
                finally:
                    db.close()

    with tab3:
        st.markdown("##### 📂 Upload an Excel file with campaign definitions")
        uploaded_file = st.file_uploader("Choose Excel File", type=['xlsx', 'xls'])
        if uploaded_file is not None:
            instructions = parse_excel_input(uploaded_file)
            st.info(f"Found **{len(instructions)}** campaigns in the file.")
            if st.button("🚀 Create All Campaigns", type="primary"):
                db = SessionLocal()
                try:
                    manager = JobManager(db)
                    for inst in instructions:
                        manager.create_campaign_and_job(inst)
                    st.success("✅ All campaigns created successfully!")
                    st.balloons()
                finally:
                    db.close()

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
                    
                    thread = threading.Thread(
                        target=run_serper_bulk, 
                        args=(job.id,),
                        daemon=True
                    )
                    thread.start()
                    
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
elif page_clean == "⚙️ Scraping Jobs":
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
                            thread = threading.Thread(target=run_job, args=(job.id,), daemon=True)
                            thread.start()
                            st.rerun()
    finally:
        db.close()


# ═══════════════════════════════════════════════
#  LEADS
# ═══════════════════════════════════════════════
elif page_clean == "🗂️ Leads":
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
            st.dataframe(df, hide_index=True, use_container_width=True)

            # Export
            csv = df.to_csv(index=False).encode('utf-8')
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
#  AI LEAD ANALYSIS
# ═══════════════════════════════════════════════
elif page_clean == "🧠 AI Lead Analysis":
    from modules.ui.ai_lead_analysis import render_ai_lead_analysis
    render_ai_lead_analysis()

# ═══════════════════════════════════════════════
#  EMAIL GENERATOR
# ═══════════════════════════════════════════════
elif page_clean == "✉️ Email Generator":
    from modules.ui.email_generator_ui import render_email_generator
    render_email_generator()

# ═══════════════════════════════════════════════
#  EMAIL DRAFTS
# ═══════════════════════════════════════════════
elif page_clean == "📝 Email Drafts":
    from modules.ui.email_drafts_ui import render_email_drafts
    render_email_drafts()

# ═══════════════════════════════════════════════
#  SEND EMAILS
# ═══════════════════════════════════════════════
elif page_clean == "📤 Send Emails":
    from modules.ui.send_emails_ui import render_send_emails
    render_send_emails()

# ═══════════════════════════════════════════════
#  EMAIL LOGS
# ═══════════════════════════════════════════════
elif page_clean == "📋 Email Logs":
    from modules.ui.email_logs_ui import render_email_logs
    render_email_logs()

# ═══════════════════════════════════════════════
#  FOLLOW-UPS
# ═══════════════════════════════════════════════
elif page_clean == "🔁 Follow-ups":
    from modules.ui.followups_ui import render_followups
    render_followups()

# ═══════════════════════════════════════════════
#  CRM PIPELINE
# ═══════════════════════════════════════════════
elif page_clean == "📈 CRM Pipeline":
    from modules.ui.crm_ui import render_crm
    render_crm()

# ═══════════════════════════════════════════════
#  SETTINGS
# ═══════════════════════════════════════════════
elif page_clean == "⚙️ Settings":
    from modules.ui.settings_ui import render_settings
    render_settings()
