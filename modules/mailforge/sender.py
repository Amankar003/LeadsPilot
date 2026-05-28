import os
import smtplib
import time
from datetime import datetime
from email.mime.text import MIMEText

from config.database import SessionLocal
from config.settings import SENDGRID_API_KEY
from modules.database.models import Lead, MailForgeDraft, MailForgeEmailLog, MailForgeSuppressionList, SenderAccount
from modules.mailforge.validators import is_valid_email


class MailForgeSender:
    def validate_sender_account(self, sender_account_id) -> dict:
        db = SessionLocal()
        try:
            account = db.query(SenderAccount).filter(SenderAccount.id == sender_account_id, SenderAccount.is_active == True).first()
            if not account:
                return {"ok": False, "error": "Sender account not found or inactive."}
            return {"ok": True, "provider": (account.provider or "smtp").lower(), "account": account}
        finally:
            db.close()

    def check_send_allowed(self, recipient_email, campaign_id, sender_account_id) -> bool:
        db = SessionLocal()
        try:
            if not is_valid_email(recipient_email):
                return False
            if db.query(MailForgeSuppressionList).filter(MailForgeSuppressionList.email == recipient_email.lower().strip()).first():
                return False
            if db.query(MailForgeEmailLog).filter(
                MailForgeEmailLog.mailforge_campaign_id == campaign_id,
                MailForgeEmailLog.recipient_email == recipient_email.lower().strip(),
                MailForgeEmailLog.status == "sent",
            ).first():
                return False
            account = db.query(SenderAccount).filter(SenderAccount.id == sender_account_id).first()
            if not account or not account.is_active:
                return False
            return int(account.sent_today or 0) < int(account.daily_limit or 100)
        finally:
            db.close()

    def _send_via_smtp(self, account, recipient, subject, body):
        username = account.smtp_username or account.email
        password = account.smtp_password
        if account.smtp_password_env_key:
            password = os.getenv(account.smtp_password_env_key, password or "")
        if not (account.smtp_host and username and password):
            return {"success": False, "error": "SMTP configuration is incomplete."}
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = account.sender_email or account.email
        msg["To"] = recipient
        with smtplib.SMTP(account.smtp_host, int(account.smtp_port or 587), timeout=20) as smtp:
            smtp.starttls()
            smtp.login(username, password)
            smtp.sendmail(msg["From"], [recipient], msg.as_string())
        return {"success": True, "provider": "smtp"}

    def _send_via_sendgrid(self, account, recipient, subject, body):
        api_key = os.getenv(account.sendgrid_api_key_env or "", "") or SENDGRID_API_KEY
        if not api_key:
            return {"success": False, "error": "SendGrid API key missing."}
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        message = Mail(
            from_email=account.sender_email or account.email,
            to_emails=recipient,
            subject=subject,
            plain_text_content=body,
        )
        response = SendGridAPIClient(api_key).send(message)
        return {"success": 200 <= response.status_code < 300, "provider": "sendgrid", "status_code": response.status_code}

    def send_draft(self, draft_id, sender_account_id, dry_run=False) -> dict:
        db = SessionLocal()
        try:
            draft = db.query(MailForgeDraft).filter(MailForgeDraft.id == draft_id).first()
            if not draft:
                return {"ok": False, "error": "Draft not found."}
            if draft.status != "approved":
                return {"ok": False, "error": "Only approved drafts can be sent."}
            lead = db.query(Lead).filter(Lead.id == draft.lead_id).first()
            recipient = lead.email if lead else None
            if not recipient or not is_valid_email(recipient):
                return {"ok": False, "error": "Recipient email is invalid."}
            if not self.check_send_allowed(recipient, draft.mailforge_campaign_id, sender_account_id):
                return {"ok": False, "error": "Send not allowed due to suppression/duplicate/limits."}
            account = db.query(SenderAccount).filter(SenderAccount.id == sender_account_id).first()
            if not account:
                return {"ok": False, "error": "Sender account not found."}
            result = {"success": True, "provider": "dry_run"} if dry_run else (
                self._send_via_sendgrid(account, recipient, draft.subject, draft.body)
                if (account.provider or "").lower() == "sendgrid"
                else self._send_via_smtp(account, recipient, draft.subject, draft.body)
            )
            db.add(
                MailForgeEmailLog(
                    mailforge_campaign_id=draft.mailforge_campaign_id,
                    lead_id=draft.lead_id,
                    draft_id=draft.id,
                    sender_account_id=sender_account_id,
                    recipient_email=recipient,
                    subject=draft.subject,
                    body=draft.body,
                    provider=result.get("provider"),
                    status="sent" if result.get("success") else "failed",
                    error_message=result.get("error"),
                    sent_at=datetime.utcnow() if result.get("success") else None,
                )
            )
            if result.get("success"):
                draft.status = "sent"
                account.sent_today = int(account.sent_today or 0) + 1
            db.commit()
            return {"ok": bool(result.get("success")), **result}
        finally:
            db.close()

    def send_batch(self, draft_ids, sender_account_id, delay_seconds=10, dry_run=False) -> list[dict]:
        results = []
        for idx, draft_id in enumerate(draft_ids):
            results.append(self.send_draft(draft_id, sender_account_id, dry_run=dry_run))
            if idx < len(draft_ids) - 1 and delay_seconds > 0:
                time.sleep(delay_seconds)
        return results
