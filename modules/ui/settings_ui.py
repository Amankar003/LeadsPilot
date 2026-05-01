import streamlit as st
import os
from config.database import SessionLocal
from config.settings import (
    DATABASE_URL, GEMINI_API_KEY, SENDGRID_API_KEY, SENDGRID_FROM_EMAIL,
    DEFAULT_EMAIL_DELAY_SECONDS, MAX_EMAILS_PER_RUN, MAX_FOLLOWUPS
)
from modules.ui.theme import page_header, empty_state, info_card


def render_settings():
    page_header("⚙️", "Settings", "System configuration, API status, and suppression list management")

    # ── System Status ──
    st.markdown("##### 🔗 System Status")
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        try:
            db = SessionLocal()
            db.execute(__import__('sqlalchemy').text("SELECT 1"))
            db.close()
            st.success("✅ Database")
        except Exception:
            st.error("❌ Database")

    with c2:
        if GEMINI_API_KEY and GEMINI_API_KEY not in ("", "your_gemini_api_key"):
            st.success("✅ Gemini AI")
        else:
            st.warning("⚠️ Gemini AI")

    with c3:
        if SENDGRID_API_KEY and SENDGRID_API_KEY not in ("", "your_sendgrid_api_key"):
            st.success("✅ SendGrid")
        else:
            st.warning("⚠️ SendGrid")

    with c4:
        if SENDGRID_FROM_EMAIL and SENDGRID_FROM_EMAIL not in ("", "hello@yourdomain.com"):
            st.success(f"✅ Sender")
        else:
            st.warning("⚠️ Sender Email")

    # ── Configuration ──
    st.divider()
    st.markdown("##### 📋 Configuration")
    c1, c2 = st.columns(2)
    with c1:
        info_card("Database", f"`{DATABASE_URL[:35]}…`")
        info_card("Gemini Model", f"`{os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')}`")
    with c2:
        info_card("Email Delay", f"{DEFAULT_EMAIL_DELAY_SECONDS} seconds between emails")
        info_card("Limits", f"Max {MAX_EMAILS_PER_RUN} emails/run • Max {MAX_FOLLOWUPS} follow-ups/lead")

    # ── Suppression List ──
    st.divider()
    st.markdown("##### 🚫 Suppression List")

    from modules.database.models import SuppressionList

    db = SessionLocal()
    try:
        suppressed = db.query(SuppressionList).all()

        if suppressed:
            st.markdown(f"**{len(suppressed)}** emails blocked from outreach:")
            sup_data = []
            for s in suppressed:
                sup_data.append({
                    "Email": s.email,
                    "Reason": s.reason,
                    "Added": str(s.created_at)[:16],
                    "ID": s.id,
                })
            sup_df = st.dataframe(
                [{"Email": s["Email"], "Reason": s["Reason"], "Added": s["Added"]} for s in sup_data],
                hide_index=True, width="stretch"
            )

            # Remove buttons
            cols = st.columns(min(len(suppressed), 4))
            for i, s in enumerate(suppressed[:4]):
                with cols[i]:
                    if st.button(f"Remove {s.email[:20]}…", key=f"unsup_{s.id}"):
                        item = db.query(SuppressionList).filter_by(id=s.id).first()
                        if item:
                            db.delete(item)
                            db.commit()
                        st.rerun()
        else:
            empty_state("🚫", "Suppression List Empty", "No emails are blocked. Blocked emails will appear here.")

        # Add to suppression
        st.markdown("")
        c_email, c_reason, c_btn = st.columns([3, 2, 1])
        with c_email:
            new_email = st.text_input("Email address", key="new_sup_email", placeholder="email@example.com", label_visibility="collapsed")
        with c_reason:
            reason = st.selectbox("Reason", ["UNSUBSCRIBED", "BOUNCED", "MANUAL_BLOCK"], key="sup_reason", label_visibility="collapsed")
        with c_btn:
            if st.button("➕ Add", use_container_width=True):
                if new_email:
                    from modules.outreach.suppression_service import SuppressionService
                    sup = SuppressionService(db)
                    if sup.is_suppressed(new_email):
                        st.warning("Already suppressed.")
                    else:
                        sup.add_to_suppression(new_email, reason)
                        st.success(f"Added {new_email}")
                        st.rerun()
                else:
                    st.warning("Enter an email.")
    finally:
        db.close()

    # ── Setup Guide ──
    st.divider()
    st.markdown("##### 📖 Setup Guide")

    with st.expander("How to configure API keys"):
        st.markdown("""
Edit your `.env` file in the project root:

```env
# AI
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.0-flash

# Email
SENDGRID_API_KEY=your_sendgrid_api_key
SENDGRID_FROM_EMAIL=hello@yourdomain.com

# Safety Limits
DEFAULT_EMAIL_DELAY_SECONDS=30
MAX_EMAILS_PER_RUN=20
MAX_FOLLOWUPS=2
```

Then restart the Streamlit app: `streamlit run app.py`
        """)

    with st.expander("Safety best practices"):
        st.markdown("""
- ✅ Always review AI-generated drafts before approving
- ✅ Keep email delay at 30+ seconds to avoid rate limits
- ✅ Send max 20-50 emails per day
- ✅ Respect unsubscribe requests immediately
- ✅ Use the suppression list for bounced/unsubscribed emails
- ❌ Never mass-send without reviewing drafts
- ❌ Never ignore bounce/spam reports
        """)
