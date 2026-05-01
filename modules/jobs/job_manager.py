import datetime
from sqlalchemy.orm import Session
from modules.database.repositories import CampaignRepository, JobRepository
from utils.constants import JOB_PENDING

class JobManager:
    def __init__(self, db: Session):
        self.db = db
        self.campaign_repo = CampaignRepository(db)
        self.job_repo = JobRepository(db)
        
    def create_campaign_and_job(self, instruction: dict):
        """
        Creates a campaign and its associated scraping job from normalized instruction.
        """
        # Create campaign
        campaign = self.campaign_repo.create(
            campaign_name=instruction['campaign_name'],
            platform=instruction['platform'],
            category=instruction['category'],
            location=instruction['location'],
            limit=instruction['limit'],
            required_fields=instruction['required_fields'],
            status="CREATED"
        )
        
        # Create job
        job = self.job_repo.create(
            campaign_id=campaign.id,
            platform=campaign.platform,
            category=campaign.category,
            location=campaign.location,
            limit=campaign.limit,
            status=JOB_PENDING
        )
        
        return campaign, job
        
    def get_all_jobs(self):
        return self.job_repo.get_all()
        
    def get_all_campaigns(self):
        return self.campaign_repo.get_all()
