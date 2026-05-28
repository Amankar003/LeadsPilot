import streamlit as st
import pandas as pd
import time
from modules.mailforge.sender import MailForgeBulkSender
from config.database import SessionLocal
from modules.database.models import MailForgeCampaign, MailForgeDraft, SenderAccount, Lead

def render_send_campaign():
    st.markdown("### 📤 Dispatch MailForge Campaign")
    st.caption("Send approved email drafts through your configured sender accounts with advanced throttling controls to protect domain reputation.")
    st.divider()

    db = SessionLocal()
    try:
        campaigns = db.query(MailForgeCampaign).order_by(MailForgeCampaign.created_at.desc()).all()
        if not campaigns:
            st.info("Please create a campaign first.")
            return

        camp_options = {c.id: c.name for c in campaigns}
        selected_campaign_id = st.selectbox(
            "🎯 Select Outreach Campaign",
            options=list(camp_options.keys()),
            format_func=lambda x: camp_options[x],
            key="send_select_camp"
        )

        # Get approved drafts
        drafts = db.query(MailForgeDraft).filter(
            MailForgeDraft.mailforge_campaign_id == selected_campaign_id,
            MailForgeDraft.status == "approved"
        ).all()

        if not drafts:
            st.warning("⚠️ No approved drafts found for this campaign! Please approve drafts in the 'Draft Review' tab first.")
            return

        st.success(f"📧 Ready to send: **{len(drafts)}** approved drafts.")

        # Select sender account
        senders = db.query(SenderAccount).filter(SenderAccount.is_active == True).all()
        if not senders:
            st.warning("⚠️ No active sender accounts configured! Please add an active SMTP sender account in the settings tab.")
            return

        sender_options = {s.id: f"{s.sender_name or 'Outreach'} <{s.email}> (Today: {s.sent_today}/{s.daily_limit})" for s in senders}
        selected_sender_id = st.selectbox(
            "📤 Select Sender Account",
            options=list(sender_options.keys()),
            format_func=lambda x: sender_options[x]
        )

        st.divider()

        # Throttling Controls
        st.markdown("#### ⚙️ Throttling & Sending Settings")
        col1, col2, col3 = st.columns(3)
        with col1:
            delay = st.slider("⏱️ Delay between emails (seconds)", min_value=2, max_value=120, value=10)
        with col2:
            batch_limit = st.number_input("📦 Maximum emails in this batch", min_value=1, max_value=500, value=50)
        with col3:
            dry_run = st.checkbox("🧪 Dry-Run Mode (Test without actually sending)", value=False, help="Simulates the campaign without hitting SMTP server.")

        st.divider()

        # Selection of drafts
        st.markdown("#### 👥 Selected Emails in this Batch")
        
        draft_rows = []
        for idx, d in enumerate(drafts[:batch_limit]):
            lead = db.query(Lead).filter(Lead.id == d.lead_id).first()
            draft_rows.append({
                "Select": True,
                "Recipient": lead.email if lead else "Unknown",
                "Business Name": lead.business_name if lead else "Unknown Business",
                "Subject": d.subject,
                "Draft ID": d.id
            })

        df_drafts = pd.DataFrame(draft_rows)
        edited_df = st.data_editor(
            df_drafts,
            column_config={
                "Select": st.column_config.CheckboxColumn(required=True)
            },
            disabled=["Recipient", "Business Name", "Subject", "Draft ID"],
            hide_index=True,
            use_container_width=True
        )

        selected_draft_ids = edited_df[edited_df["Select"]]["Draft ID"].tolist()

        if not selected_draft_ids:
            st.warning("Please select at least one draft to send.")
            return

        if st.button("🚀 Start Sending Campaign Batch", type="primary", use_container_width=True):
            progress_bar = st.progress(0.0)
            status_text = st.empty()

            sender = MailForgeBulkSender(db)
            
            success_count = 0
            failed_count = 0
            
            total_sends = len(selected_draft_ids)

            for idx, draft_id in enumerate(selected_draft_ids):
                # Throttling delay
                if idx > 0 and delay > 0:
                    status_text.text(f"Throttling Cooldown... Waiting {delay} seconds before next send...")
                    time.sleep(delay)

                # Fetch lead name to display
                d_obj = db.query(MailForgeDraft).filter(MailForgeDraft.id == draft_id).first()
                l_obj = db.query(Lead).filter(Lead.id == d_obj.lead_id).first() if d_obj else None
                rec_name = l_obj.business_name if l_obj else (d_obj.recipient_email if d_obj else "Unknown")

                status_text.text(f"Sending outreach email to {rec_name}... ({idx+1}/{total_sends})")
                progress_bar.progress((idx + 1) / total_sends)

                selected_sender_obj = db.query(SenderAccount).filter(SenderAccount.id == selected_sender_id).first()
                recipient_email = l_obj.email if l_obj else getattr(d_obj, "recipient_email", None)
                res = sender.send_one(d_obj, selected_sender_obj, recipient_email, dry_run=dry_run)
                if res["success"]:
                    success_count += 1
                else:
                    failed_count += 1
                    st.error(f"❌ Failed sending to {rec_name}: {res.get('error')}")

            st.success(f"🎉 Batch dispatch complete! Successfully Sent: **{success_count}** | Failed: **{failed_count}**")
            st.balloons()
            st.rerun()

    finally:
        db.close()
