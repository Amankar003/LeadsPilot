from sqlalchemy.orm import Session
from modules.database.repositories import SuppressionListRepository

class SuppressionService:
    def __init__(self, db: Session):
        self.repo = SuppressionListRepository(db)

    def is_suppressed(self, email: str) -> bool:
        if not email:
            return False
        return self.repo.check_email(email)

    def add_to_suppression(self, email: str, reason: str = "MANUAL_BLOCK"):
        if not email:
            return
        if not self.is_suppressed(email):
            self.repo.create(email=email, reason=reason)
