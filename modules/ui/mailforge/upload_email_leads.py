import streamlit as st
import pandas as pd
from modules.mailforge.enrichment import MailForgeEnricher
from modules.mailforge.service import MailForgeService
from config.database import SessionLocal
from modules.database.models import MailForgeCampaign

def render_upload_leads():
    st.markdown("### 📥 Upload Email-Only Leads")
    st.caption("Upload a CSV or Excel file containing email IDs or email IDs with partial business details.")
    st.divider()

    db = SessionLocal()
    try:
        campaigns = db.query(MailForgeCampaign).order_by(MailForgeCampaign.created_at.desc()).all()
        if not campaigns:
            st.warning("⚠️ No MailForge Campaign exists yet! Please create one in 'Sender Accounts & Settings' tab first.")
            return

        camp_options = {c.id: c.name for c in campaigns}
        selected_campaign_id = st.selectbox(
            "🎯 Target MailForge Campaign",
            options=list(camp_options.keys()),
            format_func=lambda x: camp_options[x]
        )

        uploaded_file = st.file_uploader("📂 Choose CSV or Excel File", type=["csv", "xlsx"])
        if uploaded_file is not None:
            # We can save to a temporary file path to use MailForgeEnricher methods
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(delete=False, suffix="." + uploaded_file.name.split(".")[-1]) as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name

            try:
                enricher = MailForgeEnricher()
                
                # Preview structure first
                if tmp_path.endswith(".csv"):
                    df = pd.read_csv(tmp_path)
                else:
                    df = pd.read_excel(tmp_path)

                st.markdown("#### 🔍 File Preview")
                st.dataframe(df.head(5), use_container_width=True)

                # Find email column
                email_col = None
                for col in df.columns:
                    col_lower = str(col).lower().strip().replace("_", "").replace("-", "")
                    if col_lower in {"email", "emailaddress", "mail", "contactemail", "emailid"}:
                        email_col = col
                        break
                if not email_col and len(df.columns) == 1:
                    email_col = df.columns[0]

                if not email_col:
                    st.error("❌ Could not automatically detect any email column! Please make sure your column is named 'email' or 'email address'.")
                    return

                emails = df[email_col].astype(str).dropna().str.strip().tolist()
                valid_emails = [e for e in emails if e and "@" in e]
                
                st.success(f"✅ Detected email column: **{email_col}**")
                st.info(f"📊 Valid emails count: **{len(valid_emails)}** / Total rows: **{len(df)}**")

                if st.button("🚀 Process and Save to MailForge Campaign", type="primary", use_container_width=True):
                    with st.spinner("Parsing and importing leads in database..."):
                        service = MailForgeService()
                        
                        # Add simple leads record mapping into MailForge leads
                        added = 0
                        from modules.database.models import MailForgeLead
                        for email in valid_emails:
                            # Avoid duplicates
                            existing = db.query(MailForgeLead).filter(
                                MailForgeLead.mailforge_campaign_id == selected_campaign_id,
                                MailForgeLead.email == email
                            ).first()
                            if existing:
                                continue
                            
                            # Guess business details
                            prefix = email.split("@")[0]
                            domain = email.split("@")[-1].lower()
                            biz_name = domain.split(".")[0].capitalize()
                            
                            mf_lead = MailForgeLead(
                                mailforge_campaign_id=selected_campaign_id,
                                email=email,
                                domain=domain,
                                business_name=biz_name,
                                enrichment_status="PENDING",
                                status="NEW"
                            )
                            db.add(mf_lead)
                            added += 1
                        
                        db.commit()
                        st.success(f"🎉 Successfully imported **{added}** unique email leads into Campaign!")
                        st.balloons()
            
            finally:
                try:
                    os.unlink(tmp_path)
                except:
                    pass
    finally:
        db.close()
