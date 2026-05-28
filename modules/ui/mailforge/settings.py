import streamlit as st
import pandas as pd
from modules.mailforge.sender import MailForgeSender
from config.database import SessionLocal
from modules.database.models import SenderAccount, MailForgeCampaign

def render_settings():
    st.markdown("### ⚙️ MailForge Campaigns & Sender settings")
    st.caption("Manage outreach campaigns, tone alignments, and safely configure SMTP or SendGrid sender credentials.")
    st.divider()

    db = SessionLocal()
    try:
        # Campaign Builder
        st.markdown("#### ➕ Create Outreach Campaign")
        with st.form("create_mailforge_camp_form"):
            col1, col2 = st.columns(2)
            with col1:
                camp_name = st.text_input("Outreach Campaign Name", placeholder="e.g. Q2 SEO Audit Pitch")
                camp_desc = st.text_area("Campaign Description", placeholder="Pitching full technical SEO audit report.")
                goal = st.selectbox("CTA Outreach Goal", [
                    "book a quick review call", "reply to get a custom video report", 
                    "give feedback on recommendations", "check out free technical audit"
                ])
            with col2:
                tone = st.selectbox("Tone Angle", ["professional", "friendly", "direct", "premium agency", "short and crisp"])
                email_length = st.selectbox("Length constraint", ["short", "medium", "detailed"])
                target_service = st.text_input("Service Offered", placeholder="e.g. Website Redesign")

            submitted = st.form_submit_button("🚀 Create outreach Campaign", type="primary", use_container_width=True)
            if submitted:
                if not camp_name:
                    st.error("Please provide a campaign name.")
                else:
                    from modules.mailforge.service import MailForgeService
                    service = MailForgeService()
                    c_id = service.create_campaign(
                        name=camp_name,
                        description=camp_desc,
                        goal=goal,
                        tone=tone,
                        email_length=email_length,
                        target_service=target_service
                    )
                    st.success(f"🎉 Created Outreach Campaign **{camp_name}** successfully!")
                    st.balloons()
                    st.rerun()

        st.divider()

        # Manage Sender Accounts
        st.markdown("#### 📤 Add Sender Account credentials")
        
        with st.form("add_sender_form"):
            col1, col2 = st.columns(2)
            with col1:
                email = st.text_input("Sender Email Address", placeholder="sender@yourcompany.com")
                sender_name = st.text_input("Display Name", placeholder="e.g. Aman Kar")
                provider = st.selectbox("Provider Engine", ["SMTP", "SendGrid"])
            with col2:
                smtp_host = st.text_input("SMTP Host", placeholder="smtp.gmail.com (leave blank for SendGrid)")
                smtp_port = st.number_input("SMTP Port", min_value=25, max_value=65535, value=587)
                password = st.text_input("SMTP Password / App Password", type="password", placeholder="Enter SMTP account password")
                sendgrid_api_key = st.text_input("SendGrid API Key (Environment key reference)", placeholder="SENDGRID_API_KEY (leave blank to read from environment)")

            submitted_sender = st.form_submit_button("➕ Save Sender Account", type="primary", use_container_width=True)
            if submitted_sender:
                if not email or "@" not in email:
                    st.error("Please enter a valid sender email.")
                else:
                    # Seed default user
                    from modules.database.models import get_or_create_default_user
                    user = get_or_create_default_user(db)
                    
                    sender = SenderAccount(
                        user_id=user.id,
                        email=email,
                        sender_email=email,
                        encrypted_password=password, # in real prod encrypt this
                        sender_name=sender_name,
                        smtp_host=smtp_host if provider == "SMTP" else None,
                        smtp_port=smtp_port if provider == "SMTP" else None,
                        provider=provider,
                        smtp_username=email,
                        sendgrid_api_key_env=sendgrid_api_key if provider == "SendGrid" else None,
                        daily_limit=100,
                        is_active=True
                    )
                    db.add(sender)
                    db.commit()
                    st.success(f"Added sender account **{email}** successfully!")
                    st.rerun()

        # Display Sender Accounts list
        st.divider()
        st.markdown("#### 👥 Configured Sender Accounts")
        senders = db.query(SenderAccount).all()
        if not senders:
            st.info("No sender accounts configured yet.")
        else:
            sender_rows = []
            for s in senders:
                sender_rows.append({
                    "Sender Name": s.sender_name or "N/A",
                    "Email": s.email,
                    "Provider": s.provider or "SMTP",
                    "Daily Limit": s.daily_limit,
                    "Sent Today": s.sent_today,
                    "Active": "🟢 Yes" if s.is_active else "🔴 No",
                    "Sender ID": s.id
                })

            df_senders = pd.DataFrame(sender_rows)
            st.dataframe(df_senders.drop(columns=["Sender ID"]), use_container_width=True)

            # Test connection / Health Check
            sender_test_id = st.selectbox("Select sender to test connection", options=[s["Sender ID"] for s in sender_rows], format_func=lambda x: [s["Email"] for s in sender_rows if s["Sender ID"] == x][0])
            
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                if st.button("🧪 Validate Connection", use_container_width=True):
                    sender_service = MailForgeSender()
                    res = sender_service.validate_sender_account(sender_test_id)
                    if res["success"]:
                        st.success(f"✅ Connection successful: {res.get('details')}")
                    else:
                        st.error(f"❌ Connection failed: {res.get('error')}")
            
            with col_t2:
                if st.button("🗑️ Delete Sender", use_container_width=True):
                    s_to_del = db.query(SenderAccount).filter(SenderAccount.id == sender_test_id).first()
                    if s_to_del:
                        db.delete(s_to_del)
                        db.commit()
                        st.warning("Sender deleted.")
                        st.rerun()

    finally:
        db.close()
