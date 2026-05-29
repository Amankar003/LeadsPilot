"""
modules/ui/mailforge/campaign_sender.py — Campaign Sender tab.
Loads approved emails from Lead Intelligence, shows stats, and lets user send them in bulk.
"""
import streamlit as st
import pandas as pd
import threading
from config.database import SessionLocal
from modules.database.models import (
    MailForgeCampaign, MailForgeDraft, MailForgeEmailLog,
    SenderAccount, Lead,
)
from modules.mailforge.sender import MailForgeBulkSender, get_setting, get_setting_int
from modules.mailforge.api_client import check_mailforge_health, send_bulk_via_mailforge_api
from modules.ui.theme import page_header, empty_state, make_dataframe_arrow_compatible
from utils.logging_utils import get_logger

logger = get_logger(__name__)


def render_campaign_sender():
    st.markdown("### 📤 Campaign Sender")
    st.caption("Load approved emails from Lead Intelligence and send them in bulk.")

    # ── MailForge Service Status ──
    is_up, status_msg = check_mailforge_health()
    if is_up:
        st.success(f"🟢 **MailForge API Connected** ({status_msg})")
    else:
        st.error(f"🔴 **MailForge API Not Running**\n\nStart it from `leadpilot-ai/mailforge` using `npm start` or `node server.js`. Error: {status_msg}")

    db = SessionLocal()
    # Cache data loading functions to avoid redundant DB hits, but we will clear them after each send.
    @st.cache_data
    def _load_campaigns():
        return db.query(MailForgeCampaign).order_by(MailForgeCampaign.created_at.desc()).all()

    @st.cache_data
    def _load_approved(campaign_id):
        engine = MailForgeBulkSender(db)
        return engine.load_approved_emails(campaign_id)

    @st.cache_data
    def _load_stats(campaign_id):
        engine = MailForgeBulkSender(db)
        return engine.get_campaign_stats(campaign_id)

    @st.cache_data
    def _load_logs(campaign_id):
        return (
            db.query(MailForgeEmailLog)
            .filter(MailForgeEmailLog.mailforge_campaign_id == campaign_id)
            .order_by(MailForgeEmailLog.created_at.desc())
            .limit(20)
            .all()
        )

    try:
        campaigns = _load_campaigns()
        sender_engine = MailForgeBulkSender(db)

        if not campaigns:
            st.info(
                "📭 No MailForge campaigns found.\n\n"
                "Go to **Lead Intelligence Report Engine** → generate and approve emails first. "
                "MailForge campaigns are auto-created when you approve emails."
            )
            return

        camp_options = {c.id: c.name for c in campaigns}
        selected_camp_id = st.selectbox(
            "🎯 Select Campaign",
            options=list(camp_options.keys()),
            format_func=lambda x: camp_options[x],
            key="mf_sender_campaign",
        )

        # ── Summary Stats ──
        accounts = sender_engine.load_sender_accounts()
        stats = _load_stats(selected_camp_id)
        daily_limit = get_setting_int(db, "emails_per_sender_per_day")
        delay = get_setting_int(db, "delay_between_emails_seconds")
        sending_mode = get_setting(db, "sending_mode")

        total_capacity = sum(
            max(0, daily_limit - (a.sent_today or 0)) for a in accounts
        )
        can_send_today = min(stats["ready_to_send"], total_capacity)
        remaining = max(0, stats["ready_to_send"] - can_send_today)
        est_minutes = (can_send_today * delay) / 60 if delay > 0 else 0

        st.divider()
        st.markdown("##### 📊 Sending Dashboard")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("✅ Approved Emails", stats["approved"])
        c2.metric("📤 Already Sent", stats["sent"])
        c3.metric("❌ Failed", stats["failed"])
        c4.metric("⏭️ Skipped", stats["skipped"])

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("🚀 Can Send Today", can_send_today)
        c6.metric("📅 Remaining Later", remaining)
        c7.metric("👤 Active Senders", len(accounts))
        c8.metric("⏱️ Est. Time", f"{est_minutes:.0f} min")

        if sending_mode == "dry_run":
            st.warning("⚠️ **Sending Mode: DRY RUN** — No real emails will be dispatched. Change in Settings.")
        else:
            st.success("🟢 **Sending Mode: LIVE** — Emails will be dispatched via SMTP.")

        # ── Approved Emails Table ──
        st.divider()
        # Use cached data loaders
        approved_drafts = _load_approved(selected_camp_id)

        if not approved_drafts:
            st.info(
                "📭 No approved emails found for this campaign.\n\n"
                "Please go to **Lead Intelligence Report Engine**, "
                "generate emails, and **approve** them first."
            )
            return

        data = []
        for draft in approved_drafts:
            lead = db.query(Lead).filter(Lead.id == draft.lead_id).first()
            recipient = lead.email if lead else "—"
            biz_name = lead.business_name if lead else "—"

            # Check last error if any
            last_log = (
                db.query(MailForgeEmailLog)
                .filter(
                    MailForgeEmailLog.draft_id == draft.id,
                    MailForgeEmailLog.status == "failed",
                )
                .order_by(MailForgeEmailLog.created_at.desc())
                .first()
            )

            data.append({
                "Select": True,
                "Draft ID": draft.id,
                "Business": biz_name,
                "Recipient": recipient,
                "Subject": (draft.subject or "")[:60],
                "Status": draft.status,
                "Last Error": (last_log.error_message[:40] if last_log and last_log.error_message else "—"),
            })

        df = pd.DataFrame(data)
        df["Select"] = df["Select"].astype(bool)

        st.markdown(f"##### ✉️ Approved Emails ({len(df)})")
        edited_df = st.data_editor(
            make_dataframe_arrow_compatible(df),
            hide_index=True,
            column_config={
                "Select": st.column_config.CheckboxColumn("Send", default=True),
                "Draft ID": st.column_config.TextColumn("Draft ID", disabled=True),
            },
            disabled=["Business", "Recipient", "Subject", "Status", "Last Error"],
            key="mf_email_editor",
        )

        selected_ids = edited_df[edited_df["Select"] == True]["Draft ID"].tolist()

        # ── Action Buttons ──
        st.divider()
        dry_run = sending_mode == "dry_run"

        col_send, col_all, col_stop = st.columns(3)

        with col_send:
            send_label = f"🚀 Send Selected ({len(selected_ids)})" if not dry_run else f"🧪 Dry Run Selected ({len(selected_ids)})"
            if st.button(send_label, type="primary", use_container_width=True, disabled=len(selected_ids) == 0):
                if not accounts:
                    st.error("No active sender accounts. Add them in the Sender Accounts tab.")
                    return
                _confirm_and_send(db, selected_ids, dry_run, len(accounts), selected_camp_id)

        with col_all:
            all_ids = [d["Draft ID"] for d in data]
            all_label = f"📨 Send All ({len(all_ids)})" if not dry_run else f"🧪 Dry Run All ({len(all_ids)})"
            if st.button(all_label, use_container_width=True, disabled=len(all_ids) == 0):
                if not accounts:
                    st.error("No active sender accounts. Add them in the Sender Accounts tab.")
                    return
                _confirm_and_send(db, all_ids, dry_run, len(accounts), selected_camp_id)

        with col_stop:
            if st.button("🛑 Stop Sending", use_container_width=True):
                st.session_state["mf_stop_sending"] = True
                st.warning("Stop signal sent. The sender will finish the current email and stop.")

        # ── Recent Logs ──
        st.divider()
        st.markdown("##### 📋 Recent Send Logs")
        # Recent send logs using cached loader
        recent_logs = _load_logs(selected_camp_id)

        if recent_logs:
            log_data = []
            for log in recent_logs:
                log_data.append({
                    "Recipient": log.recipient_email,
                    "Subject": (log.subject or "")[:50],
                    "Status": log.status,
                    "Error": (log.error_message or "")[:40],
                    "Sent At": str(log.sent_at)[:16] if log.sent_at else "—",
                })
            st.dataframe(make_dataframe_arrow_compatible(pd.DataFrame(log_data)), hide_index=True)
        else:
            st.info("No send logs yet for this campaign.")

    except Exception as e:
        logger.error(f"Error in campaign_sender: {e}", exc_info=True)
        st.error(f"⚠️ Error: {e}")
    finally:
        db.close()


def _confirm_and_send(db, draft_ids, dry_run, num_senders, campaign_id):
    """Confirmation step before sending."""
    mode_label = "DRY RUN" if dry_run else "LIVE"
    st.warning(
        f"⚠️ You are about to send **{len(draft_ids)}** emails "
        f"using **{num_senders}** sender accounts in **{mode_label}** mode."
    )

    if st.button("✅ Yes, Confirm & Start Sending", type="primary", key="mf_confirm_send"):
        if dry_run:
            st.info("Dry run requested. The API integration currently focuses on live sending, dry-run is mocked here.")
            st.cache_data.clear()
            st.rerun()
            return
            
        with st.spinner("Sending emails via Node.js MailForge API..."):
            result = send_bulk_via_mailforge_api(campaign_id, draft_ids)
            
        if not result.get("ok"):
            st.error(f"❌ Sending failed: {result.get('error', 'Unknown error')}")
            return
            
        summary = result.get("summary", {})

        st.success(
            f"✅ Batch complete — "
            f"Sent: **{summary.get('sent', 0)}** | "
            f"Failed: **{summary.get('failed', 0)}** | "
            f"Skipped: **{summary.get('skipped', 0)}**"
        )
        # Clear cached data to reflect latest DB state
        st.cache_data.clear()
        st.rerun()
