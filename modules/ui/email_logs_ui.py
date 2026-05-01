import streamlit as st
import pandas as pd
from config.database import SessionLocal
from modules.database.repositories import CampaignRepository
from modules.database.models import EmailLog, Lead
from modules.ui.theme import page_header, empty_state


def render_email_logs():
    page_header("📋", "Email Logs", "Complete audit trail of all outreach emails sent")

    db = SessionLocal()
    try:
        campaigns = CampaignRepository(db).get_all()

        if not campaigns:
            empty_state("📋", "No Campaigns", "No campaigns to show logs for.")
            return

        camp_options = {"ALL": "All Campaigns"}
        camp_options.update({c.id: c.campaign_name for c in campaigns})

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            selected = st.selectbox(
                "🎯 Campaign",
                options=list(camp_options.keys()),
                format_func=lambda x: camp_options[x],
                key="email_logs_campaign"
            )
        with col_f2:
            status_filter = st.selectbox(
                "📌 Status",
                ["ALL", "SENT", "FAILED", "BOUNCED", "REPLIED"],
                key="email_logs_status"
            )

        query = db.query(EmailLog)
        if selected != "ALL":
            query = query.filter(EmailLog.campaign_id == selected)
        if status_filter != "ALL":
            query = query.filter(EmailLog.status == status_filter)

        logs = query.order_by(EmailLog.created_at.desc()).all()

        if not logs:
            empty_state("📧", "No Email Logs", "Send some emails first to see logs here.")
            return

        # Metrics
        all_logs = db.query(EmailLog).all()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📤 Total Sent", sum(1 for l in all_logs if l.status == "SENT"))
        c2.metric("❌ Failed", sum(1 for l in all_logs if l.status == "FAILED"))
        c3.metric("💬 Replied", sum(1 for l in all_logs if l.status == "REPLIED"))
        c4.metric("📊 Total Logs", len(all_logs))

        st.divider()
        st.markdown(f"##### Showing {len(logs)} logs")

        data = []
        for log in logs:
            lead = db.query(Lead).filter_by(id=log.lead_id).first()
            status_icon = {"SENT": "✅", "FAILED": "❌", "BOUNCED": "⚠️", "REPLIED": "💬"}.get(log.status, "❓")
            data.append({
                "Status": f"{status_icon} {log.status}",
                "Recipient": log.recipient_email,
                "Business": lead.business_name if lead else "—",
                "Subject": log.subject[:40],
                "Sent At": str(log.sent_at)[:16] if log.sent_at else "—",
                "Error": log.error_message or "",
            })

        st.dataframe(pd.DataFrame(data), hide_index=True, width="stretch")
    finally:
        db.close()
