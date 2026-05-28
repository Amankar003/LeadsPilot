import streamlit as st
import pandas as pd
from config.database import SessionLocal
from modules.database.models import MailForgeCampaign, MailForgeEmailLog

def render_logs():
    st.markdown("### 📋 Outreach Email Logs")
    st.caption("A detailed, chronological registry of all B2B cold email delivery attempts and their real-time responses.")
    st.divider()

    db = SessionLocal()
    try:
        campaigns = db.query(MailForgeCampaign).order_by(MailForgeCampaign.created_at.desc()).all()
        if not campaigns:
            st.info("Please create a campaign first.")
            return

        camp_options = {"ALL": "Show All Campaigns"}
        for c in campaigns:
            camp_options[c.id] = c.name

        col1, col2 = st.columns(2)
        with col1:
            selected_campaign_id = st.selectbox(
                "🎯 Campaign Filter",
                options=list(camp_options.keys()),
                format_func=lambda x: camp_options[x],
                key="logs_select_camp"
            )
        with col2:
            status_filter = st.selectbox(
                "🚦 Delivery Status Filter",
                ["ALL", "sent", "failed"],
                key="logs_status_filter"
            )

        # Build log query
        query = db.query(MailForgeEmailLog)
        if selected_campaign_id != "ALL":
            query = query.filter(MailForgeEmailLog.mailforge_campaign_id == selected_campaign_id)
        if status_filter != "ALL":
            query = query.filter(MailForgeEmailLog.status == status_filter)

        logs = query.order_by(MailForgeEmailLog.created_at.desc()).all()

        if not logs:
            st.info("No logs matched the selected filter.")
            return

        st.markdown(f"##### Showing {len(logs)} outreach log records")
        
        log_rows = []
        for idx, l in enumerate(logs):
            log_rows.append({
                "Date": l.created_at.strftime("%Y-%m-%d %H:%M:%S") if l.created_at else "N/A",
                "Recipient": l.recipient_email,
                "Subject": l.subject,
                "Provider": l.provider or "SMTP",
                "Status": l.status.upper(),
                "Error Details": l.error_message or "Success"
            })

        st.dataframe(pd.DataFrame(log_rows), hide_index=True, use_container_width=True)

    finally:
        db.close()
