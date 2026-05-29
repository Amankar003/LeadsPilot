"""
modules/ui/mailforge/sender_accounts.py — Sender Accounts management tab.
Upload CSV/Excel of sender accounts, encrypt passwords, manage active/inactive state.
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from config.database import SessionLocal
from modules.database.models import SenderAccount, get_or_create_default_user
from utils.encryption import encrypt_value, decrypt_value
from modules.ui.theme import make_dataframe_arrow_compatible
from utils.logging_utils import get_logger

logger = get_logger(__name__)

# SMTP provider inference
PROVIDER_DEFAULTS = {
    "gmail": {"host": "smtp.gmail.com", "port": 587},
    "outlook": {"host": "smtp.office365.com", "port": 587},
    "hotmail": {"host": "smtp.office365.com", "port": 587},
    "zoho": {"host": "smtp.zoho.com", "port": 587},
    "yahoo": {"host": "smtp.mail.yahoo.com", "port": 587},
}


def _infer_provider(email: str) -> tuple[str, str, int]:
    """Infer SMTP provider, host, and port from email domain."""
    domain = email.split("@")[-1].lower() if "@" in email else ""
    for key, defaults in PROVIDER_DEFAULTS.items():
        if key in domain:
            return key, defaults["host"], defaults["port"]
    return "custom", "", 587


def render_sender_accounts():
    st.markdown("### 👤 Sender Accounts")
    st.caption("Upload and manage SMTP sender accounts for bulk email sending.")

    db = SessionLocal()
    try:
        user = get_or_create_default_user(db)

        # ── Upload CSV/Excel ──
        with st.expander("📥 Upload Sender Accounts (CSV/Excel)", expanded=False):
            st.info(
                "**Required columns:** `sender_email`, `password`\n\n"
                "**Optional columns:** `sender_name`, `provider`, `smtp_host`, `smtp_port`, "
                "`smtp_username`, `use_tls`, `daily_limit`, `is_active`\n\n"
                "Passwords will be encrypted before storage. They will never be visible in the UI."
            )

            uploaded = st.file_uploader("Choose CSV/Excel", type=["csv", "xlsx", "xls"], key="mf_sender_upload")
            if uploaded:
                try:
                    if uploaded.name.endswith('.csv'):
                        df = pd.read_csv(uploaded)
                    else:
                        df = pd.read_excel(uploaded)

                    # Normalize column names safely
                    df.columns = [str(col).strip().lower().replace(' ', '_') for col in df.columns]
                    # Alias mapping for common variations
                    alias_map = {
                        'email': 'sender_email',
                        'sender_email': 'sender_email',
                        'sender email': 'sender_email',
                        'smtp email': 'sender_email',
                        'pass': 'password',
                        'password': 'password',
                        'app_password': 'password',
                        'app password': 'password',
                        'name': 'sender_name',
                        'sender_name': 'sender_name',
                        'sender name': 'sender_name',
                        'host': 'smtp_host',
                        'smtp_host': 'smtp_host',
                        'smtp host': 'smtp_host',
                        'port': 'smtp_port',
                        'smtp_port': 'smtp_port',
                        'smtp port': 'smtp_port',
                        'username': 'smtp_username',
                        'smtp_username': 'smtp_username',
                        'smtp username': 'smtp_username',
                    }
                    # Apply aliases
                    df = df.rename(columns=lambda c: alias_map.get(c, c))

                    # Validate required columns
                    required = ['sender_email', 'password']
                    missing = [col for col in required if col not in df.columns]
                    if missing:
                        st.error(f"Missing required columns: {', '.join(missing)}. Please make sure your first row contains column headers.")
                        st.stop()

                    st.caption(f"Detected columns after normalization: {', '.join(df.columns)}")

                    st.write(f"Found **{len(df)}** accounts.")
                    # Show preview WITHOUT passwords
                    preview_cols = [c for c in df.columns if c.lower() != "password"]
                    st.dataframe(df[preview_cols].head(10), hide_index=True)

                    if st.button("💾 Save Accounts", type="primary"):
                        added, skipped = _import_sender_accounts(db, df, user.id)
                        st.success(f"✅ Added **{added}** accounts. Skipped **{skipped}** duplicates.")
                        st.rerun()
                except Exception as e:
                    st.error(f"Failed to read file: {e}")

        # ── Existing Accounts Table ──
        st.divider()
        accounts = db.query(SenderAccount).order_by(SenderAccount.created_at.desc()).all()

        if not accounts:
            st.info("No sender accounts configured. Upload a CSV/Excel above to get started.")
            return

        st.markdown(f"##### 📋 Sender Accounts ({len(accounts)})")

        data = []
        for acc in accounts:
            data.append({
                "ID": acc.id[:12],
                "Email": acc.sender_email or acc.email,
                "Provider": acc.provider or "—",
                "SMTP Host": acc.smtp_host or "—",
                "Daily Limit": acc.daily_limit or 100,
                "Sent Today": acc.sent_today or 0,
                "Status": "✅ Active" if acc.is_active else "❌ Inactive",
                "Last Used": str(acc.updated_at)[:16] if acc.updated_at else "—",
                "Full ID": acc.id,
            })

        df_accounts = pd.DataFrame(data)
        st.dataframe(
            make_dataframe_arrow_compatible(df_accounts.drop(columns=["Full ID"])),
            hide_index=True,
        )

        # ── Actions ──
        st.divider()
        st.markdown("##### ⚙️ Account Actions")

        col_id, col_action = st.columns([2, 1])
        with col_id:
            acc_id_input = st.selectbox(
                "Select Account",
                options=[a.id for a in accounts],
                format_func=lambda x: next(
                    (f"{a.sender_email or a.email}" for a in accounts if a.id == x), x
                ),
                key="mf_acc_select",
            )
        with col_action:
            action = st.selectbox(
                "Action",
                ["Test Connection", "Activate", "Deactivate", "Delete"],
                key="mf_acc_action",
            )

        if st.button("▶️ Execute Action", use_container_width=True):
            account = db.query(SenderAccount).filter(SenderAccount.id == acc_id_input).first()
            if not account:
                st.error("Account not found.")
            elif action == "Test Connection":
                _test_smtp_connection(account)
            elif action == "Activate":
                account.is_active = True
                db.commit()
                st.success(f"✅ Activated: {account.sender_email or account.email}")
                st.rerun()
            elif action == "Deactivate":
                account.is_active = False
                db.commit()
                st.warning(f"❌ Deactivated: {account.sender_email or account.email}")
                st.rerun()
            elif action == "Delete":
                db.delete(account)
                db.commit()
                st.success(f"🗑️ Deleted: {account.sender_email or account.email}")
                st.rerun()

    except Exception as e:
        logger.error(f"Error in sender_accounts: {e}", exc_info=True)
        st.error(f"⚠️ Error: {e}")
    finally:
        db.close()


def _import_sender_accounts(db, df: pd.DataFrame, user_id: str) -> tuple[int, int]:
    """Import sender accounts from a DataFrame, encrypting passwords."""
    added = 0
    skipped = 0

    for _, row in df.iterrows():
        sender_email = str(row.get("sender_email", "")).strip()
        password = str(row.get("password", "")).strip()

        if not sender_email or not password:
            skipped += 1
            continue

        # Check duplicate
        existing = db.query(SenderAccount).filter(
            SenderAccount.sender_email == sender_email
        ).first()
        if existing:
            skipped += 1
            continue

        # Infer provider if not provided
        provider_raw = str(row.get("provider", "")).strip()
        smtp_host_raw = str(row.get("smtp_host", "")).strip()
        smtp_port_raw = row.get("smtp_port", None)

        if not provider_raw or not smtp_host_raw:
            inferred_provider, inferred_host, inferred_port = _infer_provider(sender_email)
            if not provider_raw:
                provider_raw = inferred_provider
            if not smtp_host_raw:
                smtp_host_raw = inferred_host
            if not smtp_port_raw:
                smtp_port_raw = inferred_port

        smtp_username = str(row.get("smtp_username", "")).strip() or sender_email
        daily_limit_raw = row.get("daily_limit", None)
        try:
            daily_limit = int(daily_limit_raw)
        except (ValueError, TypeError):
            daily_limit = 40

        is_active_raw = str(row.get("is_active", "true")).strip().lower()
        is_active = is_active_raw in ("true", "1", "yes", "")

        sender_name = str(row.get("sender_name", "")).strip() or None

        # Encrypt the password
        encrypted_pw = encrypt_value(password)

        account = SenderAccount(
            user_id=user_id,
            email=sender_email,
            sender_email=sender_email,
            sender_name=sender_name,
            encrypted_password=encrypted_pw,
            smtp_username=smtp_username,
            smtp_host=smtp_host_raw or None,
            smtp_port=int(smtp_port_raw or 587),
            provider=provider_raw or None,
            daily_limit=daily_limit,
            is_active=is_active,
        )
        db.add(account)
        added += 1

    db.commit()
    return added, skipped


def _test_smtp_connection(account: SenderAccount):
    """Test the SMTP connection for a sender account."""
    import smtplib

    try:
        password = decrypt_value(account.encrypted_password) if account.encrypted_password else ""
        if not password:
            password = account.smtp_password or ""

        smtp_host = account.smtp_host or "smtp.gmail.com"
        smtp_port = int(account.smtp_port or 587)
        smtp_user = account.smtp_username or account.sender_email or account.email

        with st.spinner(f"Testing connection to {smtp_host}:{smtp_port}..."):
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as smtp:
                smtp.starttls()
                smtp.login(smtp_user, password)
                smtp.noop()

        st.success(f"✅ Connection successful for **{account.sender_email or account.email}**!")

    except Exception as e:
        error_msg = str(e)
        # Never expose password in the error message
        if account.encrypted_password:
            pw = decrypt_value(account.encrypted_password)
            if pw and pw in error_msg:
                error_msg = error_msg.replace(pw, "***")
        st.error(f"❌ Connection failed: {error_msg}")
