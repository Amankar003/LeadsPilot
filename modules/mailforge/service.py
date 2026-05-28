from config.database import SessionLocal
from modules.database.models import (
    MailForgeCampaign, MailForgeLead, MailForgeDraft,
    MailForgeFollowUp, Lead
)
from modules.mailforge.enrichment import MailForgeEnricher
from modules.mailforge.generator import MailForgeGenerator
from modules.mailforge.followups import MailForgeFollowUpService
from utils.logging_utils import get_logger

logger = get_logger(__name__)

class MailForgeService:
    def __init__(self):
        self.enricher = MailForgeEnricher()
        self.generator = MailForgeGenerator()
        self.followup_service = MailForgeFollowUpService()

    def create_campaign(self, name: str, description: str = None, goal: str = None, tone: str = None, email_length: str = None, target_service: str = None, sender_profile: dict = None) -> str:
        """
        Creates a new MailForge Campaign.
        """
        db = SessionLocal()
        try:
            import json
            campaign = MailForgeCampaign(
                name=name,
                description=description,
                goal=goal,
                tone=tone,
                email_length=email_length,
                target_service=target_service,
                sender_profile=json.dumps(sender_profile) if sender_profile else None,
                status="CREATED"
            )
            db.add(campaign)
            db.commit()
            db.refresh(campaign)
            return campaign.id
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create campaign: {e}")
            raise e
        finally:
            db.close()

    def send_leads_to_mailforge(self, mailforge_campaign_id: str, lead_ids: list[str]) -> int:
        """
        Import general/scraped leads into a MailForge campaign.
        """
        db = SessionLocal()
        added = 0
        try:
            campaign = db.query(MailForgeCampaign).filter(MailForgeCampaign.id == mailforge_campaign_id).first()
            if not campaign:
                logger.error("Campaign not found")
                return 0

            for l_id in lead_ids:
                lead = db.query(Lead).filter(Lead.id == l_id).first()
                if not lead or not lead.email:
                    continue

                # Avoid duplicate import in same campaign
                existing = db.query(MailForgeLead).filter(
                    MailForgeLead.mailforge_campaign_id == mailforge_campaign_id,
                    MailForgeLead.email == lead.email
                ).first()
                if existing:
                    continue

                mf_lead = MailForgeLead(
                    mailforge_campaign_id=mailforge_campaign_id,
                    lead_id=lead.id,
                    email=lead.email,
                    business_name=lead.business_name,
                    website=lead.website,
                    domain=lead.domain,
                    enrichment_status="enriched" if lead.website else "partial",
                    confidence_score=0.9 if lead.website else 0.5,
                    status="NEW"
                )
                db.add(mf_lead)
                added += 1

            db.commit()
            return added
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to send leads to MailForge: {e}")
            return 0
        finally:
            db.close()

    def generate_emails_for_campaign(self, mailforge_campaign_id: str, progress_callback=None) -> dict:
        """
        Generate AI cold outreach drafts and follow-ups for all leads associated with a campaign.
        """
        db = SessionLocal()
        summary = {"success": 0, "failed": 0}
        try:
            campaign = db.query(MailForgeCampaign).filter(MailForgeCampaign.id == mailforge_campaign_id).first()
            if not campaign:
                return {"error": "Campaign not found"}

            import json
            sender_profile = {}
            if campaign.sender_profile:
                try:
                    sender_profile = json.loads(campaign.sender_profile)
                except:
                    pass

            campaign_config = {
                "tone": campaign.tone,
                "email_length": campaign.email_length,
                "goal": campaign.goal,
                "target_service": campaign.target_service
            }

            # Fetch campaign leads that don't have drafts yet
            leads = db.query(MailForgeLead).filter(
                MailForgeLead.mailforge_campaign_id == mailforge_campaign_id
            ).all()

            total_leads = len(leads)
            if total_leads == 0:
                return {"success": 0, "failed": 0, "notes": "No leads in this campaign."}

            for idx, mf_lead in enumerate(leads):
                # Check if draft already exists
                existing_draft = db.query(MailForgeDraft).filter(
                    MailForgeDraft.mailforge_campaign_id == mailforge_campaign_id,
                    MailForgeDraft.lead_id == mf_lead.lead_id
                ).first()
                if existing_draft:
                    continue

                if progress_callback:
                    progress_callback(f"Generating email for {mf_lead.business_name or mf_lead.email} ({idx+1}/{total_leads})", idx / total_leads)

                try:
                    # Convert lead to dictionary
                    lead_dict = {
                        "id": mf_lead.lead_id,
                        "email": mf_lead.email,
                        "business_name": mf_lead.business_name,
                        "website": mf_lead.website,
                        "domain": mf_lead.domain,
                        "category": campaign.target_service
                    }

                    # Call generator
                    email_data = self.generator.generate_email(lead_dict, campaign_config, sender_profile)

                    # Save Draft
                    draft = MailForgeDraft(
                        mailforge_campaign_id=mailforge_campaign_id,
                        lead_id=mf_lead.lead_id,
                        subject=email_data.get("subject", "Connecting"),
                        body=email_data.get("body", ""),
                        opening_line=email_data.get("opening_line", ""),
                        cta=email_data.get("cta", ""),
                        personalization_reason=email_data.get("personalization_reason", ""),
                        confidence_score=email_data.get("confidence_score", 0.5),
                        status="draft",
                        version=1
                    )
                    db.add(draft)
                    db.flush()

                    # Save Follow-ups
                    self.followup_service.create_followups_for_draft(draft.id, email_data.get("followups", []))
                    
                    mf_lead.status = "GENERATED"
                    summary["success"] += 1
                except Exception as e:
                    logger.error(f"Failed to generate email for {mf_lead.email}: {e}")
                    summary["failed"] += 1

            db.commit()
            return summary
        except Exception as e:
            db.rollback()
            logger.error(f"Generate emails job failed: {e}")
            return {"error": str(e)}
        finally:
            db.close()
