import streamlit as st
import pandas as pd
from modules.mailforge.analytics import MailForgeAnalytics
from config.database import SessionLocal
from modules.database.models import MailForgeCampaign, MailForgeEmailLog

def render_dashboard():
    st.markdown("### 📊 MailForge outreach Dashboard")
    st.divider()

    analytics = MailForgeAnalytics()
    stats = analytics.get_dashboard_stats()

    # Metrics row 1
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 Total Leads in MailForge", stats["total_leads"])
    c2.metric("📝 Drafts Generated", stats["total_drafts"])
    c3.metric("✅ Emails Approved", stats["approved_drafts"])
    c4.metric("📤 Sent Emails", stats["sent_emails"])

    # Metrics row 2
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("❌ Failed Sends", stats["failed_emails"])
    c6.metric("🔁 Follow-ups Pending", stats["pending_followups"])
    c7.metric("🚫 Suppressed Emails", stats["suppressed_emails"])
    c8.metric("🎯 Total Campaigns", stats["total_campaigns"])

    st.divider()
    
    # Non-configured tracking metrics (Placeholder)
    st.markdown("#### 📈 Conversion & Tracking")
    ct1, ct2, ct3 = st.columns(3)
    ct1.info("📧 **Open Rate:** Not configured yet")
    ct2.info("🔗 **Click Rate:** Not configured yet")
    ct3.info("💬 **Reply Rate:** Not configured yet")

    st.divider()

    db = SessionLocal()
    try:
        # Recent MailForge Campaigns
        st.markdown("#### 🎯 Recent MailForge Campaigns")
        campaigns = db.query(MailForgeCampaign).order_by(MailForgeCampaign.created_at.desc()).limit(5).all()
        if campaigns:
            camp_data = []
            for c in campaigns:
                camp_data.append({
                    "Campaign ID": c.id[:8] + "...",
                    "Name": c.name,
                    "Tone": c.tone or "N/A",
                    "Target Service": c.target_service or "N/A",
                    "Status": c.status,
                    "Created At": str(c.created_at)[:16]
                })
            st.dataframe(pd.DataFrame(camp_data), hide_index=True, use_container_width=True)
        else:
            st.info("No MailForge campaigns found yet. Create one in the settings or send leads from CRM.")

        # Recent Logs & Failed Sends
        st.markdown("#### 📋 Recent Outreach Email Logs")
        logs = db.query(MailForgeEmailLog).order_by(MailForgeEmailLog.created_at.desc()).limit(5).all()
        if logs:
            log_data = []
            for l in logs:
                log_data.append({
                    "Recipient": l.recipient_email,
                    "Subject": l.subject[:40] + "...",
                    "Provider": l.provider or "SMTP",
                    "Status": l.status.upper(),
                    "Error": l.error_message or "None",
                    "Sent At": str(l.sent_at)[:16] if l.sent_at else "N/A"
                })
            st.dataframe(pd.DataFrame(log_data), hide_index=True, use_container_width=True)
        else:
            st.info("No email sending logs recorded yet.")

    finally:
        db.close()
