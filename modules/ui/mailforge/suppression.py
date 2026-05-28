import streamlit as st
import pandas as pd
from modules.mailforge.suppression import MailForgeSuppressionService

def render_suppression():
    st.markdown("### 🚫 Suppression List Management")
    st.caption("Avoid blacklisting by suppressing unsubscribed leads, bounced email addresses, manual blocks, and spam complaints.")
    st.divider()

    suppression_service = MailForgeSuppressionService()

    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### ➕ Add Email Manually")
        with st.form("add_suppression_form"):
            email = st.text_input("Recipient Email", placeholder="lead@company.com")
            reason = st.selectbox("Reason", [
                "unsubscribe", "bounce", "manual_block", 
                "invalid_email", "do_not_contact", "spam_complaint"
            ])
            notes = st.text_area("Notes", placeholder="e.g. Lead unsubscribed via contact page.")
            
            submitted = st.form_submit_button("🚫 Suppress Email", type="primary", use_container_width=True)
            if submitted:
                if not email or "@" not in email:
                    st.error("Please enter a valid email address.")
                else:
                    success = suppression_service.add_email(email, reason, notes)
                    if success:
                        st.success(f"Added **{email}** to suppression list.")
                        st.rerun()
                    else:
                        st.error("Failed to add to suppression list.")

    with col2:
        st.markdown("#### 📥 Import Suppression CSV")
        uploaded_file = st.file_uploader("Choose CSV file of emails to block", type=["csv"])
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
                # Find email column
                email_col = None
                for col in df.columns:
                    if "email" in str(col).lower():
                        email_col = col
                        break
                if not email_col and len(df.columns) == 1:
                    email_col = df.columns[0]

                if not email_col:
                    st.error("Could not find email column.")
                else:
                    emails = df[email_col].astype(str).dropna().str.strip().tolist()
                    valid_emails = [e for e in emails if e and "@" in e]
                    
                    if st.button(f"🚫 Suppress {len(valid_emails)} Emails", use_container_width=True):
                        added = suppression_service.bulk_add(valid_emails, "manual_block")
                        st.success(f"Blocked **{added}** unique emails in bulk.")
                        st.rerun()
            except Exception as e:
                st.error(f"Error reading file: {e}")

    st.divider()

    # View suppressed emails
    st.markdown("#### 🚫 Suppressed Emails Registry")
    records = suppression_service.list_suppressed()
    
    if not records:
        st.info("No suppressed emails recorded.")
    else:
        rec_data = []
        for r in records:
            rec_data.append({
                "Email": r["email"],
                "Reason": r["reason"].upper(),
                "Notes": r["notes"] or "None",
                "Suppressed Since": r["created_at"].strftime("%Y-%m-%d %H:%M") if r["created_at"] else "N/A",
                "Actions": r["email"]
            })

        df_rec = pd.DataFrame(rec_data)
        st.dataframe(df_rec.drop(columns=["Actions"]), use_container_width=True)

        st.markdown("##### Remove Email from Suppression")
        to_remove = st.selectbox("Select email to remove", options=[r["email"] for r in records])
        if st.button("🔓 Remove Selected Email Block", type="secondary", use_container_width=True):
            if suppression_service.remove_email(to_remove):
                st.success(f"Removed **{to_remove}** from suppression.")
                st.rerun()
            else:
                st.error("Failed to remove email block.")
