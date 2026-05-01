from sqlalchemy.orm import Session
from modules.database.repositories import LeadRepository, CRMActivityRepository

class CRMService:
    def __init__(self, db: Session):
        self.lead_repo = LeadRepository(db)
        self.activity_repo = CRMActivityRepository(db)

    def update_lead_status(self, lead_id: str, campaign_id: str, status: str, note: str = ""):
        self.lead_repo.update_status(lead_id, status)
        self.activity_repo.create(
            lead_id=lead_id,
            campaign_id=campaign_id,
            activity_type="STATUS_CHANGE",
            description=f"Status changed to {status}. {note}"
        )
        
    def add_activity(self, lead_id: str, campaign_id: str, activity_type: str, description: str, metadata: dict = None):
        self.activity_repo.create(
            lead_id=lead_id,
            campaign_id=campaign_id,
            activity_type=activity_type,
            description=description,
            metadata_json=metadata or {}
        )
