import streamlit as st
import pandas as pd
from config.database import SessionLocal
from modules.database.repositories import (
    CampaignRepository, EmailLogRepository, FollowUpRepository, LeadRepository
)
from modules.database.models import EmailLog, Lead, FollowUp
from modules.ai.email_generator import EmailGenerator
from modules.outreach.email_sender import EmailSender
from modules.crm.pipeline import CRMService
from modules.ui.theme import page_header, empty_state
from config.settings import MAX_FOLLOWUPS
import datetime


def render_followups():
    page_header("🔁", "Follow-ups", "Generate and send follow-up emails to non-responsive leads")

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
            key="followups_campaign"
        )

        followup_repo = FollowUpRepository(db)
        lead_repo = LeadRepository(db)

        sent_logs = db.query(EmailLog).filter(
            EmailLog.campaign_id == selected_camp_id,
            EmailLog.status == "SENT"
        ).all()

        if not sent_logs:
            empty_state("📤", "No Sent Emails", "Send emails first before creating follow-ups.")
            return

        # Find leads needing follow-ups
        needs_followup = []
        skip_statuses = ("REPLIED", "MEETING_BOOKED", "CLOSED_WON", "CLOSED_LOST", "DO_NOT_CONTACT", "NOT_INTERESTED")
        for log in sent_logs:
            lead = db.query(Lead).filter_by(id=log.lead_id).first()
            if not lead or lead.status in skip_statuses:
                continue
            existing = db.query(FollowUp).filter(
                FollowUp.lead_id == log.lead_id,
                FollowUp.campaign_id == selected_camp_id
            ).count()
            if existing < MAX_FOLLOWUPS:
                needs_followup.append({"log": log, "lead": lead, "followup_number": existing + 1})

        c1, c2, c3 = st.columns(3)
        c1.metric("📤 Sent Emails", len(sent_logs))
        c2.metric("🔁 Eligible", len(needs_followup))
        c3.metric("📊 Max Follow-ups", MAX_FOLLOWUPS)

        # ── Generate follow-ups ──
        if needs_followup:
            st.divider()
            st.markdown("##### 🔁 Generate Follow-ups")
            data = []
            for item in needs_followup:
                data.append({
                    "Select": False,
                    "Lead ID": item["lead"].id,
                    "Log ID": item["log"].id,
                    "Business": item["lead"].business_name,
                    "Email": item["log"].recipient_email,
                    "Follow-up #": item["followup_number"],
                    "Original Subject": item["log"].subject[:40],
                })

            df = pd.DataFrame(data)
            edited_df = st.data_editor(
                df, hide_index=True, width="stretch",
                column_config={"Select": st.column_config.CheckboxColumn("✓", default=False)},
                key="followup_editor"
            )

            selected_rows = edited_df[edited_df["Select"] == True].to_dict('records')

            if st.button("🔁 Generate Follow-up Emails", type="primary", use_container_width=True):
                if not selected_rows:
                    st.warning("Select leads first.")
                else:
                    generator = EmailGenerator()
                    progress = st.progress(0, text="Generating…")

                    for i, row in enumerate(selected_rows):
                        log_entry = db.query(EmailLog).filter_by(id=row["Log ID"]).first()
                        lead = db.query(Lead).filter_by(id=row["Lead ID"]).first()
                        progress.progress(
                            (i + 1) / len(selected_rows),
                            text=f"🔁 Follow-up {i + 1}/{len(selected_rows)}: {lead.business_name[:25]}…" if lead else "Working…"
                        )

                        if log_entry and lead:
                            lead_data = {"business_name": lead.business_name, "category": lead.category, "email": lead.email, "website": lead.website}
                            fup_data = generator.generate_followup(lead_data, log_entry.subject, log_entry.body, row["Follow-up #"])

                            followup_repo.create(
                                lead_id=lead.id,
                                campaign_id=selected_camp_id,
                                parent_email_log_id=log_entry.id,
                                followup_number=row["Follow-up #"],
                                subject=fup_data.get("subject", f"Re: {log_entry.subject}"),
                                body=fup_data.get("body", "Following up."),
                                status="GENERATED",
                            )
                            lead_repo.update_status(lead.id, "FOLLOWUP_PENDING")

                    progress.progress(1.0, text="✅ Follow-ups generated!")
                    st.rerun()

        # ── Pending follow-ups ──
        st.divider()
        st.markdown("##### 📬 Pending Follow-ups")
        pending = db.query(FollowUp).filter(
            FollowUp.campaign_id == selected_camp_id,
            FollowUp.status.in_(["PENDING", "GENERATED"])
        ).all()

        if not pending:
            empty_state("📬", "No Pending Follow-ups", "Generate follow-ups above or all have been sent.")
        else:
            for fup in pending:
                lead = db.query(Lead).filter_by(id=fup.lead_id).first()
                biz = lead.business_name if lead else "Unknown"
                with st.expander(f"🔁 #{fup.followup_number} — {biz}"):
                    st.markdown(f"**Subject:** {fup.subject}")
                    st.code(fup.body, language=None)

                    c1, c2, _ = st.columns([1, 1, 2])
                    with c1:
                        if st.button("📤 Send", key=f"send_fup_{fup.id}", type="primary", use_container_width=True):
                            if lead and lead.email:
                                sender = EmailSender()
                                result = sender.send_email(lead.email, fup.subject, fup.body)
                                if result.get("success"):
                                    fup.status = "SENT"
                                    fup.sent_at = datetime.datetime.utcnow()
                                    db.commit()
                                    EmailLogRepository(db).create(
                                        lead_id=lead.id, campaign_id=selected_camp_id,
                                        recipient_email=lead.email, subject=fup.subject, body=fup.body,
                                        provider_message_id=result.get("message_id"),
                                        status="SENT", sent_at=datetime.datetime.utcnow(),
                                    )
                                    CRMService(db).update_lead_status(lead.id, selected_camp_id, "FOLLOWUP_SENT")
                                    st.success("✅ Follow-up sent!")
                                    st.rerun()
                                else:
                                    fup.status = "FAILED"
                                    db.commit()
                                    st.error(f"Failed: {result.get('error')}")
                            else:
                                st.error("No email for this lead.")
                    with c2:
                        if st.button("❌ Cancel", key=f"cancel_fup_{fup.id}", use_container_width=True):
                            fup.status = "CANCELLED"
                            db.commit()
                            st.rerun()
    finally:
        db.close()
