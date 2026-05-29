import streamlit as st
import os
from config.database import SessionLocal
from config.settings import (
    DATABASE_URL, GROQ_API_KEY, GROQ_MODEL
)
from modules.ui.theme import page_header, empty_state, info_card, make_dataframe_arrow_compatible
import pandas as pd


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
        if GROQ_API_KEY and GROQ_API_KEY not in ("", "your_groq_api_key_here"):
            try:
                from modules.ai.ai_client import AIClient
                client = AIClient()
                health = client.health_check()
                if health.get("status") == "success":
                    st.success("✅ Groq AI")
                else:
                    st.warning(f"⚠️ Groq AI: {health.get('message', 'Failed')}")
            except:
                st.warning("⚠️ Groq AI")
        else:
            st.error("❌ Groq AI")

    with c3:
        st.empty()

    with c4:
        st.empty()

    # ── Configuration ──
    st.divider()
    st.markdown("##### 📋 Configuration")
    c1, c2 = st.columns(2)
    with c1:
        info_card("Database", f"`{DATABASE_URL[:35]}…`")
        info_card("Groq Model", f"`{GROQ_MODEL}`")
    with c2:
        info_card("Export Format", "CSV (receiverid, subject, body)")
        info_card("Email Sending", "Handled externally via CSV export")


    # ── Setup Guide ──
    st.divider()
    st.markdown("##### 📖 Setup Guide")

    with st.expander("How to configure API keys"):
        st.markdown("""
Edit your `.env` file in the project root:

```env
# AI
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# Email Settings
# Email sending is handled externally using downloaded CSVs.

# Safety Limits
DEFAULT_EMAIL_DELAY_SECONDS=30
MAX_EMAILS_PER_RUN=20
MAX_FOLLOWUPS=2
```

Then restart the Streamlit app: `streamlit run app.py`
        """)

    with st.expander("Safety best practices"):
        st.markdown("""
- ✅ Always review AI-generated drafts before exporting
- ✅ Use the CSV export to send campaigns through your preferred external provider
- ❌ Never mass-send without reviewing drafts
        """)
