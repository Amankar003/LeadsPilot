from config.database import SessionLocal
from modules.database.models import (
    MailForgeCampaign, MailForgeLead, MailForgeDraft,
    MailForgeFollowUp, MailForgeEmailLog, MailForgeSuppressionList,
    SenderAccount
)
from utils.logging_utils import get_logger

logger = get_logger(__name__)

class MailForgeAnalytics:
    def get_dashboard_stats(self) -> dict:
        """
        Calculates aggregate counts dynamically from MailForge tables.
        """
        db = SessionLocal()
        try:
            total_leads = db.query(MailForgeLead).count()
            total_drafts = db.query(MailForgeDraft).count()
            approved_drafts = db.query(MailForgeDraft).filter(MailForgeDraft.status == "approved").count()
            sent_emails = db.query(MailForgeEmailLog).filter(MailForgeEmailLog.status == "sent").count()
            failed_emails = db.query(MailForgeEmailLog).filter(MailForgeEmailLog.status == "failed").count()
            pending_followups = db.query(MailForgeFollowUp).filter(MailForgeFollowUp.status == "pending").count()
            suppressed = db.query(MailForgeSuppressionList).count()
            total_campaigns = db.query(MailForgeCampaign).count()

            return {
                "total_leads": total_leads,
                "total_drafts": total_drafts,
                "approved_drafts": approved_drafts,
                "sent_emails": sent_emails,
                "failed_emails": failed_emails,
                "pending_followups": pending_followups,
                "suppressed_emails": suppressed,
                "total_campaigns": total_campaigns
            }
        except Exception as e:
            logger.error(f"Error compiling dashboard stats: {e}")
            return {
                "total_leads": 0, "total_drafts": 0, "approved_drafts": 0,
                "sent_emails": 0, "failed_emails": 0, "pending_followups": 0,
                "suppressed_emails": 0, "total_campaigns": 0
            }
        finally:
            db.close()

    def get_campaign_stats(self, mailforge_campaign_id: str) -> dict:
        """
        Calculate metrics for a single campaign.
        """
        db = SessionLocal()
        try:
            leads = db.query(MailForgeLead).filter(MailForgeLead.mailforge_campaign_id == mailforge_campaign_id).count()
            drafts = db.query(MailForgeDraft).filter(MailForgeDraft.mailforge_campaign_id == mailforge_campaign_id).count()
            sent = db.query(MailForgeEmailLog).filter(
                MailForgeEmailLog.mailforge_campaign_id == mailforge_campaign_id,
                MailForgeEmailLog.status == "sent"
            ).count()
            failed = db.query(MailForgeEmailLog).filter(
                MailForgeEmailLog.mailforge_campaign_id == mailforge_campaign_id,
                MailForgeEmailLog.status == "failed"
            ).count()
            
            return {
                "leads": leads,
                "drafts": drafts,
                "sent": sent,
                "failed": failed
            }
        except Exception as e:
            logger.error(f"Error fetching campaign stats: {e}")
            return {"leads": 0, "drafts": 0, "sent": 0, "failed": 0}
        finally:
            db.close()

    def get_sender_stats(self, sender_account_id: str) -> dict:
        """
        Calculate metrics for a specific sender account.
        """
        db = SessionLocal()
        try:
            sender = db.query(SenderAccount).filter(SenderAccount.id == sender_account_id).first()
            if not sender:
                return {}

            total_sent = db.query(MailForgeEmailLog).filter(
                MailForgeEmailLog.sender_account_id == sender_account_id,
                MailForgeEmailLog.status == "sent"
            ).count()
            total_failed = db.query(MailForgeEmailLog).filter(
                MailForgeEmailLog.sender_account_id == sender_account_id,
                MailForgeEmailLog.status == "failed"
            ).count()

            return {
                "email": sender.email,
                "sender_name": sender.sender_name,
                "daily_limit": sender.daily_limit,
                "sent_today": sender.sent_today,
                "total_sent": total_sent,
                "total_failed": total_failed,
                "is_active": sender.is_active
            }
        except Exception as e:
            logger.error(f"Error fetching sender stats: {e}")
            return {}
        finally:
            db.close()
