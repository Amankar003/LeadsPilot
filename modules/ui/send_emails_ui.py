import streamlit as st
import pandas as pd
from config.database import SessionLocal
from modules.database.repositories import CampaignRepository, EmailDraftRepository, EmailLogRepository, LeadRepository
from modules.database.models import EmailDraft, Lead
from modules.outreach.email_sender import EmailSender
from modules.outreach.suppression_service import SuppressionService
from modules.crm.pipeline import CRMService
from modules.ui.theme import page_header, empty_state, workflow_indicator
from utils.logging_utils import get_logger
import time
import datetime
from config.settings import DEFAULT_EMAIL_DELAY_SECONDS, MAX_EMAILS_PER_RUN

logger = get_logger(__name__)


def render_send_emails():
    page_header("📤", "Send Emails", "Send approved email drafts via SendGrid with built-in safety controls")

    workflow_indicator(
        ["Scrape", "Clean", "AI Analyze", "Generate Email", "Review", "Send"],
        active_index=5
    )

    db = SessionLocal()
    try:
        campaigns = CampaignRepository(db).get_all()

        if not campaigns:
            empty_state("📋", "No Campaigns", "Create a campaign first.")
            return

        camp_options = {c.id: c.campaign_name for c in campaigns}
        selected_camp_id = st.selectbox(
            "🎯 Select Campaign",
            options=list(camp_options.keys()),
            format_func=lambda x: camp_options[x],
            key="send_emails_campaign"
        )

        drafts = db.query(EmailDraft).filter(
            EmailDraft.campaign_id == selected_camp_id,
            EmailDraft.status == "APPROVED"
        ).all()

        if not drafts:
            empty_state("✅", "No Approved Drafts", "Approve drafts first in the Email Drafts page.")
            return

        st.markdown(f"##### {len(drafts)} approved emails ready to send")

        # Safety controls
        st.markdown("##### ⚙️ Send Controls")
        c1, c2 = st.columns(2)
        with c1:
            delay = st.number_input("⏱️ Delay between emails (seconds)", min_value=0, value=DEFAULT_EMAIL_DELAY_SECONDS, help="Prevents rate limiting")
        with c2:
            max_run = st.number_input("📊 Max emails this run", min_value=1, max_value=100, value=MAX_EMAILS_PER_RUN, help="Safety limit per session")

        st.divider()

        data = []
        for d in drafts:
            lead = db.query(Lead).filter_by(id=d.lead_id).first()
            if lead and lead.email:
                data.append({
                    "Select": False,
                    "Draft ID": d.id,
                    "Lead ID": lead.id,
                    "Business Name": lead.business_name,
                    "Email": lead.email,
                    "Subject": d.subject[:50],
                })

        if not data:
            empty_state("📧", "No Valid Emails", "No approved drafts have valid email addresses.")
            return

        df = pd.DataFrame(data)
        edited_df = st.data_editor(
            df, hide_index=True, width="stretch",
            column_config={"Select": st.column_config.CheckboxColumn("✓", default=False)},
            key="send_emails_editor"
        )

        selected_drafts = edited_df[edited_df["Select"] == True].to_dict('records')

        st.markdown("")
        if st.button(f"📤 Send {len(selected_drafts)} Email{'s' if len(selected_drafts) != 1 else ''}", type="primary", use_container_width=True, disabled=(len(selected_drafts) == 0)):
            if len(selected_drafts) > max_run:
                st.warning(f"Selected {len(selected_drafts)} but max is {max_run}.")
            else:
                sender = EmailSender()
                suppression = SuppressionService(db)
                crm = CRMService(db)
                log_repo = EmailLogRepository(db)
                draft_repo = EmailDraftRepository(db)

                progress = st.progress(0, text="Preparing to send…")
                success_count = 0

                for i, item in enumerate(selected_drafts):
                    email_addr = item['Email']
                    progress.progress(
                        (i + 1) / len(selected_drafts),
                        text=f"📤 Sending {i + 1}/{len(selected_drafts)} to {email_addr}…"
                    )

                    if suppression.is_suppressed(email_addr):
                        logger.warning(f"Skipping {email_addr} — suppressed.")
                        st.warning(f"⚠️ Skipped {email_addr} (suppressed)")
                        continue

                    lead = db.query(Lead).filter_by(id=item['Lead ID']).first()
                    if lead and lead.status == "DO_NOT_CONTACT":
                        st.warning(f"⚠️ Skipped {email_addr} (Do Not Contact)")
                        continue

                    draft = draft_repo.get_by_id(item['Draft ID'])
                    result = sender.send_email(email_addr, draft.subject, draft.body)

                    if result.get("success"):
                        log_repo.create(
                            lead_id=item['Lead ID'], campaign_id=selected_camp_id,
                            email_draft_id=draft.id, recipient_email=email_addr,
                            subject=draft.subject, body=draft.body,
                            provider_message_id=result.get("message_id"),
                            status="SENT", sent_at=datetime.datetime.utcnow(),
                        )
                        draft_repo.update(draft.id, status="SENT")
                        crm.update_lead_status(item['Lead ID'], selected_camp_id, "EMAIL_SENT")
                        success_count += 1
                    else:
                        log_repo.create(
                            lead_id=item['Lead ID'], campaign_id=selected_camp_id,
                            email_draft_id=draft.id, recipient_email=email_addr,
                            subject=draft.subject, body=draft.body,
                            status="FAILED", error_message=result.get("error", "Unknown"),
                        )

                    if i < len(selected_drafts) - 1:
                        time.sleep(delay)

                progress.progress(1.0, text=f"✅ Done! Sent {success_count}/{len(selected_drafts)} emails.")
                time.sleep(2)
                st.rerun()
    finally:
        db.close()
