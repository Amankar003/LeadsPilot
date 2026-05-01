import streamlit as st
import pandas as pd
import threading
from config.database import SessionLocal
from modules.database.db_init import init_db
from modules.database.repositories import CampaignRepository, JobRepository, LeadRepository
from modules.input.manual_input import parse_manual_input
from modules.input.excel_parser import parse_excel_input
from modules.jobs.job_manager import JobManager
from modules.jobs.scraping_planner import ScrapingPlanner
from utils.constants import PLATFORM_GOOGLE_MAPS
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

    tab1, tab2 = st.tabs(["✍️ Manual Input", "📂 Excel Upload"])

    with tab1:
        with st.form("manual_campaign_form"):
            st.markdown("##### Campaign Details")
            col1, col2 = st.columns(2)
            with col1:
                campaign_name = st.text_input("Campaign Name", "Delhi Salon Leads", help="A descriptive name for this campaign")
                category = st.text_input("Business Category", "Salons", help="What type of business to scrape")
            with col2:
                platform = st.selectbox("Platform", [PLATFORM_GOOGLE_MAPS])
                location = st.text_input("Location", "Delhi", help="City or area to target")

            col3, col4 = st.columns(2)
            with col3:
                limit = st.number_input("Lead Limit", min_value=1, max_value=5000, value=100, help="Max number of leads to scrape")
            with col4:
                req_fields_str = st.text_input("Required Fields", "business_name,phone,website,email,address")

            submitted = st.form_submit_button("🚀 Create Campaign", type="primary", use_container_width=True)
            if submitted:
                req_fields = [f.strip() for f in req_fields_str.split(",")]
                instruction = parse_manual_input(campaign_name, platform, category, location, limit, req_fields)
                db = SessionLocal()
                try:
                    manager = JobManager(db)
                    campaign, job = manager.create_campaign_and_job(instruction)
                    st.success(f"✅ Campaign **{campaign.campaign_name}** created! Job ID: `{job.id[:8]}…`")
                    st.balloons()
                finally:
                    db.close()

    with tab2:
        st.markdown("##### Upload an Excel file with campaign definitions")
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
                data.append({
                    "Business Name": l.business_name,
                    "Category": l.category,
                    "Phone": l.phone or "",
                    "Email": l.email or "",
                    "Website": l.website or "",
                    "Location": l.address or "",
                    "Rating": l.rating or "",
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
            st.dataframe(df, hide_index=True, width="stretch")

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
