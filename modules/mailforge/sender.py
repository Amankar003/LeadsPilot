"""
modules/mailforge/sender.py — MailForge Bulk Email Sending Engine.

This module is the production-grade bulk sender that:
  1. Loads approved MailForgeDrafts for a given campaign.
  2. Assigns sender accounts using configurable rotation strategies.
  3. Sends emails via SMTP with rate-limiting, daily limits, and suppression checks.
  4. Supports dry-run mode and failure-rate circuit-breaking.
"""
import os
import smtplib
import time
from datetime import datetime, date

def safe_date(value):
    """Convert various date representations to a date object safely. Returns None if conversion fails."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except Exception:
            return None
    return None

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from sqlalchemy.orm import Session

from modules.database.models import (
    Lead, MailForgeDraft, MailForgeEmailLog, MailForgeSuppressionList,
    SenderAccount, MailForgeSetting,
)
from modules.mailforge.validators import is_valid_email
from utils.encryption import decrypt_value
from utils.logging_utils import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────
# Settings Helpers
# ──────────────────────────────────────────────

DEFAULT_SETTINGS = {
    "emails_per_sender_per_day": ("40", "int"),
    "delay_between_emails_seconds": ("30", "int"),
    "batch_size": ("50", "int"),
    "retry_failed_emails": ("true", "bool"),
    "max_retry_count": ("2", "int"),
    "skip_duplicate_recipients": ("true", "bool"),
    "skip_suppressed_emails": ("true", "bool"),
    "stop_on_high_failure_rate": ("true", "bool"),
    "failure_rate_threshold_percent": ("30", "int"),
    "sending_mode": ("dry_run", "string"),
    "sender_rotation_strategy": ("round_robin", "string"),
    "default_smtp_host": ("smtp.gmail.com", "string"),
    "default_smtp_port": ("587", "int"),
    "use_tls": ("true", "bool"),
}


def get_setting(db: Session, key: str) -> str:
    """Get a single MailForge setting from DB, falling back to defaults."""
    row = db.query(MailForgeSetting).filter(MailForgeSetting.key == key).first()
    if row:
        return row.value
    default = DEFAULT_SETTINGS.get(key)
    return default[0] if default else ""


def get_setting_int(db: Session, key: str) -> int:
    try:
        return int(get_setting(db, key))
    except (ValueError, TypeError):
        return int(DEFAULT_SETTINGS.get(key, ("0",))[0])


def get_setting_bool(db: Session, key: str) -> bool:
    return get_setting(db, key).lower() in ("true", "1", "yes")


def get_all_settings(db: Session) -> dict:
    """Return all settings as a dict, merging DB values with defaults."""
    result = {}
    for key, (default_val, val_type) in DEFAULT_SETTINGS.items():
        row = db.query(MailForgeSetting).filter(MailForgeSetting.key == key).first()
        result[key] = row.value if row else default_val
    return result


def save_setting(db: Session, key: str, value: str):
    """Upsert a single setting."""
    row = db.query(MailForgeSetting).filter(MailForgeSetting.key == key).first()
    if row:
        row.value = value
        row.updated_at = datetime.utcnow()
    else:
        val_type = DEFAULT_SETTINGS.get(key, ("", "string"))[1]
        db.add(MailForgeSetting(key=key, value=value, value_type=val_type))
    db.commit()


# ──────────────────────────────────────────────
# Bulk Sender Class
# ──────────────────────────────────────────────

class MailForgeBulkSender:
    """Production-grade bulk email sender for approved MailForge drafts."""

    def __init__(self, db: Session):
        self.db = db
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True

    # ── Loading ──────────────────────────────

    def load_approved_emails(self, campaign_id: str) -> list[MailForgeDraft]:
        """Load approved drafts that haven't been sent yet for a campaign."""
        return (
            self.db.query(MailForgeDraft)
            .filter(
                MailForgeDraft.mailforge_campaign_id == campaign_id,
                MailForgeDraft.status.in_(["approved", "ready"]),
            )
            .all()
        )

    def load_sender_accounts(self) -> list[SenderAccount]:
        """Load all active sender accounts."""
        today = date.today()
        accounts = (
            self.db.query(SenderAccount)
            .filter(SenderAccount.is_active == True)
            .all()
        )
        # Reset daily counters if the day has changed
        for acc in accounts:
            if acc.last_reset_date is None or safe_date(acc.last_reset_date) < today:
                acc.sent_today = 0
                acc.last_reset_date = datetime.utcnow()
        self.db.commit()
        return accounts

    # ── Sender Assignment ────────────────────

    def assign_senders(
        self, drafts: list[MailForgeDraft], accounts: list[SenderAccount]
    ) -> list[tuple[MailForgeDraft, SenderAccount]]:
        """Assign sender accounts to drafts using the configured rotation strategy."""
        strategy = get_setting(self.db, "sender_rotation_strategy")
        daily_limit = get_setting_int(self.db, "emails_per_sender_per_day")

        # Filter accounts that still have capacity
        available = [a for a in accounts if (a.sent_today or 0) < daily_limit]
        if not available:
            return []

        assignments = []
        if strategy == "least_used_today":
            for draft in drafts:
                available.sort(key=lambda a: a.sent_today or 0)
                best = available[0]
                if (best.sent_today or 0) >= daily_limit:
                    break
                assignments.append((draft, best))
                best.sent_today = (best.sent_today or 0) + 1
        else:
            # round_robin (default)
            idx = 0
            for draft in drafts:
                sender = available[idx % len(available)]
                if (sender.sent_today or 0) >= daily_limit:
                    # Try to find next available sender
                    found = False
                    for offset in range(1, len(available)):
                        candidate = available[(idx + offset) % len(available)]
                        if (candidate.sent_today or 0) < daily_limit:
                            sender = candidate
                            found = True
                            break
                    if not found:
                        break
                assignments.append((draft, sender))
                sender.sent_today = (sender.sent_today or 0) + 1
                idx += 1

        # Reset the virtual counts we incremented during assignment
        for acc in accounts:
            acc_db = self.db.query(SenderAccount).filter(SenderAccount.id == acc.id).first()
            if acc_db:
                acc.sent_today = acc_db.sent_today
        self.db.expire_all()

        return assignments

    # ── Sending ──────────────────────────────

    def send_selected(
        self, draft_ids: list[str], dry_run: bool = False,
        progress_callback=None,
    ) -> dict:
        """
        Send selected approved drafts.
        Returns summary dict with total/sent/failed/skipped counts.
        """
        self._stop_requested = False
        accounts = self.load_sender_accounts()
        if not accounts:
            return {"total": 0, "sent": 0, "failed": 0, "skipped": 0, "error": "No active sender accounts."}

        # Debug logging
        logger.debug(f"Sending selected drafts IDs: {draft_ids}")
        drafts = (
            self.db.query(MailForgeDraft)
            .filter(
                MailForgeDraft.id.in_(draft_ids),
                MailForgeDraft.status == "approved",
            )
            .all()
        )

        delay = get_setting_int(self.db, "delay_between_emails_seconds")
        skip_dup = get_setting_bool(self.db, "skip_duplicate_recipients")
        skip_sup = get_setting_bool(self.db, "skip_suppressed_emails")
        stop_high_fail = get_setting_bool(self.db, "stop_on_high_failure_rate")
        fail_threshold = get_setting_int(self.db, "failure_rate_threshold_percent")
        daily_limit = get_setting_int(self.db, "emails_per_sender_per_day")

        assignments = self.assign_senders(drafts, accounts)

        summary = {"total": len(draft_ids), "sent": 0, "failed": 0, "skipped": 0, "stopped": False}
        sent_recipients = set()

        for i, (draft, sender) in enumerate(assignments):
            if self._stop_requested:
                summary["stopped"] = True
                break

            lead = self.db.query(Lead).filter(Lead.id == draft.lead_id).first()
            recipient = lead.email if lead else None

            # Validation checks
            if not recipient or not is_valid_email(recipient):
                self._log_attempt(draft, sender, "skipped", error="Invalid/missing recipient email")
                summary["skipped"] += 1
                continue

            recipient_lower = recipient.lower().strip()

            if skip_sup and self._is_suppressed(recipient_lower):
                self._log_attempt(draft, sender, "suppressed", error="Suppressed email")
                draft.status = "suppressed"
                self.db.commit()
                summary["skipped"] += 1
                continue

            if skip_dup and recipient_lower in sent_recipients:
                self._log_attempt(draft, sender, "skipped", error="Duplicate recipient in this batch")
                summary["skipped"] += 1
                continue

            # Check sender daily limit (real-time)
            real_sender = self.db.query(SenderAccount).filter(SenderAccount.id == sender.id).first()
            if (real_sender.sent_today or 0) >= daily_limit:
                self._log_attempt(draft, sender, "skipped", error="Sender daily limit reached")
                summary["skipped"] += 1
                continue

            # Send
            result = self.send_one(draft, real_sender, recipient, dry_run=dry_run)

            if result.get("success"):
                summary["sent"] += 1
                sent_recipients.add(recipient_lower)
            else:
                summary["failed"] += 1

            if progress_callback:
                progress_callback(i + 1, len(assignments), summary)

            # Circuit breaker
            processed = summary["sent"] + summary["failed"]
            if stop_high_fail and processed >= 5:
                fail_rate = (summary["failed"] / processed) * 100
                if fail_rate >= fail_threshold:
                    logger.warning(f"High failure rate ({fail_rate:.0f}%) — stopping batch.")
                    summary["stopped"] = True
                    break

            # Delay between emails
            if i < len(assignments) - 1 and delay > 0 and not dry_run:
                time.sleep(delay)

        return summary

    def send_one(
        self, draft: MailForgeDraft, sender: SenderAccount,
        recipient: str, dry_run: bool = False
    ) -> dict:
        """Send a single email via SMTP (or simulate in dry-run mode)."""
        if dry_run:
            self._log_attempt(draft, sender, "dry_run")
            draft.status = "dry_run"
            self.db.commit()
            return {"success": True, "provider": "dry_run"}

        try:
            password = decrypt_value(sender.encrypted_password) if sender.encrypted_password else ""
            if not password:
                # Fallback to smtp_password or env key
                password = sender.smtp_password or ""
                if sender.smtp_password_env_key:
                    password = os.getenv(sender.smtp_password_env_key, password)

            smtp_host = sender.smtp_host or get_setting(self.db, "default_smtp_host")
            smtp_port = int(sender.smtp_port or get_setting_int(self.db, "default_smtp_port"))
            smtp_user = sender.smtp_username or sender.sender_email or sender.email
            from_email = sender.sender_email or sender.email
            use_tls = get_setting_bool(self.db, "use_tls")

            msg = MIMEMultipart("alternative")
            msg["Subject"] = draft.subject
            msg["From"] = from_email
            msg["To"] = recipient
            msg.attach(MIMEText(draft.body, "html", "utf-8"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as smtp:
                if use_tls:
                    smtp.starttls()
                smtp.login(smtp_user, password)
                smtp.sendmail(from_email, [recipient], msg.as_string())

            # Update statuses
            self._log_attempt(draft, sender, "sent")
            draft.status = "sent"
            sender_db = self.db.query(SenderAccount).filter(SenderAccount.id == sender.id).first()
            sender_db.sent_today = (sender_db.sent_today or 0) + 1
            sender_db.updated_at = datetime.utcnow()
            self.db.commit()
            return {"success": True, "provider": "smtp"}

        except Exception as e:
            error_msg = str(e)
            # Never expose password in error messages
            if password and password in error_msg:
                error_msg = error_msg.replace(password, "***")
            logger.error(f"SMTP send failed for {recipient}: {error_msg}")
            # Update draft status to failed
            draft.status = "failed"
            self._log_attempt(draft, sender, "failed", error=error_msg)
            self.db.commit()
            return {"success": False, "error": error_msg}

    # ── Helpers ──────────────────────────────

    def _is_suppressed(self, email: str) -> bool:
        return (
            self.db.query(MailForgeSuppressionList)
            .filter(MailForgeSuppressionList.email == email)
            .first()
        ) is not None

    def _log_attempt(
        self, draft: MailForgeDraft, sender: SenderAccount,
        status: str, error: str = None
    ):
        lead = self.db.query(Lead).filter(Lead.id == draft.lead_id).first()
        recipient = lead.email if lead else "unknown"
        self.db.add(MailForgeEmailLog(
            mailforge_campaign_id=draft.mailforge_campaign_id,
            lead_id=draft.lead_id,
            draft_id=draft.id,
            sender_account_id=sender.id,
            recipient_email=recipient,
            subject=draft.subject,
            body=draft.body,
            provider=sender.provider or "smtp",
            status=status,
            error_message=error,
            sent_at=datetime.utcnow() if status == "sent" else None,
        ))

    def get_campaign_stats(self, campaign_id: str) -> dict:
        """Return sending statistics for a campaign."""
        approved = (
            self.db.query(MailForgeDraft)
            .filter(
                MailForgeDraft.mailforge_campaign_id == campaign_id,
                MailForgeDraft.status == "approved",
            ).count()
        )
        sent = (
            self.db.query(MailForgeEmailLog)
            .filter(
                MailForgeEmailLog.mailforge_campaign_id == campaign_id,
                MailForgeEmailLog.status == "sent",
            ).count()
        )
        failed = (
            self.db.query(MailForgeEmailLog)
            .filter(
                MailForgeEmailLog.mailforge_campaign_id == campaign_id,
                MailForgeEmailLog.status == "failed",
            ).count()
        )
        skipped = (
            self.db.query(MailForgeEmailLog)
            .filter(
                MailForgeEmailLog.mailforge_campaign_id == campaign_id,
                MailForgeEmailLog.status.in_(["skipped", "suppressed"]),
            ).count()
        )
        return {
            "approved": approved,
            "sent": sent,
            "failed": failed,
            "skipped": skipped,
            "ready_to_send": approved,
        }
# Backwards compatibility alias for refactored sender
MailForgeSender = MailForgeBulkSender
