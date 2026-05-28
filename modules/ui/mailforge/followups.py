import streamlit as st
import pandas as pd
from config.database import SessionLocal
from modules.database.models import MailForgeCampaign, MailForgeFollowUp, Lead

def render_followups():
    st.markdown("### 🔁 MailForge Follow-up Sequences")
    st.caption("Review, edit, or approve follow-up emails that are automatically scheduled to go out after a set number of days if the recipient has not replied.")
    st.divider()

    db = SessionLocal()
    try:
        campaigns = db.query(MailForgeCampaign).order_by(MailForgeCampaign.created_at.desc()).all()
        if not campaigns:
            st.info("Please create a campaign first.")
            return

        camp_options = {c.id: c.name for c in campaigns}
        selected_campaign_id = st.selectbox(
            "🎯 Select Campaign",
            options=list(camp_options.keys()),
            format_func=lambda x: camp_options[x],
            key="fups_select_camp"
        )

        # Get follow-ups
        followups = db.query(MailForgeFollowUp).filter(
            MailForgeFollowUp.mailforge_campaign_id == selected_campaign_id
        ).order_by(MailForgeFollowUp.followup_number.asc()).all()

        if not followups:
            st.info("No follow-ups found for this campaign yet. Once cold emails are generated, follow-up steps are scheduled automatically.")
            return

        # Simple status metrics
        f_counts = {}
        for f in followups:
            f_counts[f.status] = f_counts.get(f.status, 0) + 1

        c1, c2, c3 = st.columns(3)
        c1.metric("Pending", f_counts.get("pending", 0))
        c2.metric("Approved", f_counts.get("approved", 0))
        c3.metric("Sent", f_counts.get("sent", 0))

        st.divider()
        st.markdown(f"##### Showing {len(followups)} scheduled follow-ups")

        for idx, fup in enumerate(followups):
            lead = db.query(Lead).filter(Lead.id == fup.lead_id).first()
            recipient_email = lead.email if lead else "Unknown"
            biz_name = lead.business_name if lead else "Unknown Business"
            
            status_emoji = {
                "pending": "⏳", "approved": "✅", "sent": "📤", "failed": "⚠️", "skipped": "⏩"
            }.get(fup.status, "🔁")

            with st.expander(f"{status_emoji} Step {fup.followup_number} for {biz_name} — After {fup.scheduled_after_days} Days"):
                st.markdown(f"**Recipient:** {recipient_email}")
                new_subject = st.text_input("Follow-up Subject", value=fup.subject, key=f"fup_subj_{fup.id}_{idx}")
                new_body = st.text_area("Follow-up Body", value=fup.body, height=200, key=f"fup_body_{fup.id}_{idx}")

                col_b1, col_b2, col_b3, _ = st.columns([1, 1, 1, 1])
                with col_b1:
                    if st.button("💾 Save Changes", key=f"fup_save_{fup.id}_{idx}", use_container_width=True):
                        fup.subject = new_subject
                        fup.body = new_body
                        db.commit()
                        st.success("Follow-up saved!")
                
                with col_b2:
                    if fup.status == "pending":
                        if st.button("✅ Approve Follow-up", key=f"fup_app_{fup.id}_{idx}", use_container_width=True, type="primary"):
                            fup.status = "approved"
                            db.commit()
                            st.success("Follow-up approved!")
                            st.rerun()

                with col_b3:
                    if fup.status != "sent":
                        if st.button("⏩ Skip/Cancel", key=f"fup_skip_{fup.id}_{idx}", use_container_width=True):
                            fup.status = "skipped"
                            db.commit()
                            st.warning("Follow-up skipped.")
                            st.rerun()

    finally:
        db.close()
