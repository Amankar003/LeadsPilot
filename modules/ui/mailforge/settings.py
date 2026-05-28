"""
modules/ui/mailforge/settings.py — MailForge Bulk Sending Settings.
Manages the key-value settings for sending behavior.
"""
import streamlit as st
from config.database import SessionLocal
from modules.mailforge.sender import (
    get_all_settings, save_setting, DEFAULT_SETTINGS,
)
from utils.logging_utils import get_logger

logger = get_logger(__name__)


def render_settings():
    st.markdown("### ⚙️ MailForge Settings")
    st.caption("Configure the bulk email sending engine's behavior, limits, and safety features.")

    db = SessionLocal()
    try:
        current = get_all_settings(db)

        with st.form("mf_settings_form"):
            st.markdown("##### 📨 Sending Limits")
            col1, col2, col3 = st.columns(3)
            with col1:
                emails_per_day = st.number_input(
                    "Emails per sender per day",
                    min_value=1, max_value=500,
                    value=int(current.get("emails_per_sender_per_day", 40)),
                    key="mf_s_epd",
                )
            with col2:
                delay = st.number_input(
                    "Delay between emails (seconds)",
                    min_value=0, max_value=300,
                    value=int(current.get("delay_between_emails_seconds", 30)),
                    key="mf_s_delay",
                )
            with col3:
                batch_size = st.number_input(
                    "Batch size",
                    min_value=1, max_value=1000,
                    value=int(current.get("batch_size", 50)),
                    key="mf_s_batch",
                )

            st.markdown("##### 🔁 Retry & Deduplication")
            col4, col5 = st.columns(2)
            with col4:
                retry_failed = st.checkbox(
                    "Retry failed emails",
                    value=current.get("retry_failed_emails", "true").lower() == "true",
                    key="mf_s_retry",
                )
                max_retry = st.number_input(
                    "Max retry count",
                    min_value=0, max_value=10,
                    value=int(current.get("max_retry_count", 2)),
                    key="mf_s_maxretry",
                )
            with col5:
                skip_dup = st.checkbox(
                    "Skip duplicate recipients",
                    value=current.get("skip_duplicate_recipients", "true").lower() == "true",
                    key="mf_s_skipdup",
                )
                skip_sup = st.checkbox(
                    "Skip suppressed emails",
                    value=current.get("skip_suppressed_emails", "true").lower() == "true",
                    key="mf_s_skipsup",
                )

            st.markdown("##### 🛡️ Safety & Circuit Breaker")
            col6, col7 = st.columns(2)
            with col6:
                stop_high_fail = st.checkbox(
                    "Stop on high failure rate",
                    value=current.get("stop_on_high_failure_rate", "true").lower() == "true",
                    key="mf_s_stophigh",
                )
                fail_threshold = st.number_input(
                    "Failure rate threshold (%)",
                    min_value=5, max_value=100,
                    value=int(current.get("failure_rate_threshold_percent", 30)),
                    key="mf_s_failthresh",
                )
            with col7:
                sending_mode = st.selectbox(
                    "Sending Mode",
                    options=["dry_run", "live"],
                    index=0 if current.get("sending_mode", "dry_run") == "dry_run" else 1,
                    key="mf_s_mode",
                )
                rotation = st.selectbox(
                    "Sender Rotation Strategy",
                    options=["round_robin", "least_used_today"],
                    index=0 if current.get("sender_rotation_strategy", "round_robin") == "round_robin" else 1,
                    key="mf_s_rotation",
                )

            st.markdown("##### 📡 Default SMTP Configuration")
            col8, col9, col10 = st.columns(3)
            with col8:
                default_host = st.text_input(
                    "Default SMTP Host",
                    value=current.get("default_smtp_host", "smtp.gmail.com"),
                    key="mf_s_host",
                )
            with col9:
                default_port = st.number_input(
                    "Default SMTP Port",
                    min_value=25, max_value=65535,
                    value=int(current.get("default_smtp_port", 587)),
                    key="mf_s_port",
                )
            with col10:
                use_tls = st.checkbox(
                    "Use TLS",
                    value=current.get("use_tls", "true").lower() == "true",
                    key="mf_s_tls",
                )

            submitted = st.form_submit_button("💾 Save Settings", type="primary", use_container_width=True)

            if submitted:
                settings_to_save = {
                    "emails_per_sender_per_day": str(emails_per_day),
                    "delay_between_emails_seconds": str(delay),
                    "batch_size": str(batch_size),
                    "retry_failed_emails": str(retry_failed).lower(),
                    "max_retry_count": str(max_retry),
                    "skip_duplicate_recipients": str(skip_dup).lower(),
                    "skip_suppressed_emails": str(skip_sup).lower(),
                    "stop_on_high_failure_rate": str(stop_high_fail).lower(),
                    "failure_rate_threshold_percent": str(fail_threshold),
                    "sending_mode": sending_mode,
                    "sender_rotation_strategy": rotation,
                    "default_smtp_host": default_host,
                    "default_smtp_port": str(default_port),
                    "use_tls": str(use_tls).lower(),
                }
                for key, val in settings_to_save.items():
                    save_setting(db, key, val)

                st.success("✅ Settings saved successfully!")
                st.rerun()

        # ── Current Settings Summary ──
        st.divider()
        st.markdown("##### 📄 Current Configuration")
        refreshed = get_all_settings(db)
        summary_data = [{"Setting": k, "Value": v} for k, v in refreshed.items()]
        st.dataframe(summary_data, hide_index=True, use_container_width=True)

    except Exception as e:
        logger.error(f"Error in settings: {e}", exc_info=True)
        st.error(f"⚠️ Error: {e}")
    finally:
        db.close()
