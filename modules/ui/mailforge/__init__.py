import streamlit as st

from modules.ui.mailforge.dashboard import render_dashboard
from modules.ui.mailforge.upload_email_leads import render_upload_leads
from modules.ui.mailforge.enrichment_ui import render_enrichment
from modules.ui.mailforge.generate_emails import render_generate_emails
from modules.ui.mailforge.drafts import render_drafts
from modules.ui.mailforge.send_campaign import render_send_campaign
from modules.ui.mailforge.followups import render_followups
from modules.ui.mailforge.logs import render_logs
from modules.ui.mailforge.suppression import render_suppression
from modules.ui.mailforge.settings import render_settings

def render_mailforge():
    """
    Consolidated entry point for MailForge Streamlit UI.
    Renders the tabbed interface inside Streamlit.
    """
    st.markdown("## 🔥 MailForge outreach Engine")
    st.caption("AI-Powered lead enrichment, personalized cold email sequences, and safe sending.")

    tabs = st.tabs([
        "📊 Dashboard",
        "📥 Upload Leads",
        "🌐 Email-Only Enrichment",
        "🧠 Generate AI Emails",
        "📝 Draft Review",
        "📤 Send Campaign",
        "🔁 Follow-ups",
        "📋 Logs",
        "🚫 Suppression List",
        "⚙️ Sender Accounts & Settings"
    ])

    with tabs[0]:
        render_dashboard()

    with tabs[1]:
        render_upload_leads()

    with tabs[2]:
        render_enrichment()

    with tabs[3]:
        render_generate_emails()

    with tabs[4]:
        render_drafts()

    with tabs[5]:
        render_send_campaign()

    with tabs[6]:
        render_followups()

    with tabs[7]:
        render_logs()

    with tabs[8]:
        render_suppression()

    with tabs[9]:
        render_settings()
