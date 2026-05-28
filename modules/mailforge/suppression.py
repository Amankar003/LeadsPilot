from config.database import SessionLocal
from modules.database.models import MailForgeSuppressionList
from utils.logging_utils import get_logger

logger = get_logger(__name__)

class MailForgeSuppressionService:
    def add_email(self, email: str, reason: str, notes: str = None) -> bool:
        """
        Add a single email to the suppression list.
        """
        email = str(email).strip().lower()
        if not email or "@" not in email:
            return False

        db = SessionLocal()
        try:
            existing = db.query(MailForgeSuppressionList).filter(
                MailForgeSuppressionList.email == email
            ).first()
            if existing:
                existing.reason = reason
                existing.notes = notes
                db.commit()
                return True

            domain = email.split("@")[-1]
            suppressed = MailForgeSuppressionList(
                email=email,
                domain=domain,
                reason=reason,
                notes=notes
            )
            db.add(suppressed)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to add email {email} to suppression list: {e}")
            return False
        finally:
            db.close()

    def remove_email(self, email: str) -> bool:
        """
        Remove an email from the suppression list.
        """
        email = str(email).strip().lower()
        db = SessionLocal()
        try:
            suppressed = db.query(MailForgeSuppressionList).filter(
                MailForgeSuppressionList.email == email
            ).first()
            if suppressed:
                db.delete(suppressed)
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to remove email {email} from suppression list: {e}")
            return False
        finally:
            db.close()

    def is_suppressed(self, email: str) -> bool:
        """
        Checks if the email is suppressed.
        """
        email = str(email).strip().lower()
        if not email:
            return False
        db = SessionLocal()
        try:
            suppressed = db.query(MailForgeSuppressionList).filter(
                MailForgeSuppressionList.email == email
            ).first()
            return suppressed is not None
        finally:
            db.close()

    def bulk_add(self, emails: list[str], reason: str) -> int:
        """
        Adds multiple emails in bulk to suppression.
        """
        added = 0
        for email in emails:
            if self.add_email(email, reason):
                added += 1
        return added

    def list_suppressed(self) -> list[dict]:
        """
        Returns all suppressed records as dictionaries.
        """
        db = SessionLocal()
        try:
            records = db.query(MailForgeSuppressionList).order_by(
                MailForgeSuppressionList.created_at.desc()
            ).all()
            return [
                {
                    "id": r.id,
                    "email": r.email,
                    "domain": r.domain,
                    "reason": r.reason,
                    "notes": r.notes,
                    "created_at": r.created_at
                }
                for r in records
            ]
        finally:
            db.close()
