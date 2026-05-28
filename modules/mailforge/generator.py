import json
import os
from modules.ai.ai_client import AIClient
from modules.database.models import Lead, LeadInsight, AnalysisReport
from config.database import SessionLocal
from utils.logging_utils import get_logger

logger = get_logger(__name__)

class MailForgeGenerator:
    def __init__(self):
        self.ai = AIClient()

    def generate_email(self, lead: dict, campaign_config: dict, sender_profile: dict = None) -> dict:
        """
        Generates cold email subject, body, opening line, CTA, and follow-ups.
        Uses technical website audit info if available, otherwise falls back to highly clean templates.
        """
        # Ensure lead is standard dict
        lead_name = lead.get("business_name") or lead.get("name") or "Business Owner"
        website = lead.get("website") or "No website found"
        category = lead.get("category") or "services"
        location = lead.get("location") or "your area"

        # Check database for existing AI audits / insights to include in prompt
        audit_details = ""
        db = SessionLocal()
        try:
            # Try to get lead record from DB
            db_lead = db.query(Lead).filter(
                (Lead.email == lead.get("email")) | (Lead.id == lead.get("id"))
            ).first()
            if db_lead:
                # 1. Check LeadInsight
                insight = db.query(LeadInsight).filter(LeadInsight.lead_id == db_lead.id).first()
                if insight:
                    audit_details += f"\n- Recommended Service focus: {insight.recommended_service}"
                    audit_details += f"\n- Pain Points identified: {', '.join(insight.pain_points) if insight.pain_points else 'None'}"
                    audit_details += f"\n- Lead Score / Level: {insight.lead_score} ({insight.lead_type})"
                
                # 2. Check AnalysisReport
                report = db.query(AnalysisReport).filter(AnalysisReport.lead_id == db_lead.id).first()
                if report and report.has_website:
                    audit_details += f"\n- Overall Technical Score: {report.overall_score}/100"
                    audit_details += f"\n- Opportunity Level: {report.opportunity_level}"
                    audit_details += f"\n- Key Technical Pain Points: {json.dumps(report.pain_points_json)}"
                    audit_details += f"\n- Recommended Solutions: {json.dumps(report.recommended_services_json)}"
        except Exception as e:
            logger.warning(f"Error querying db for lead details: {e}")
        finally:
            db.close()

        # Build clean campaign variables
        tone = campaign_config.get("tone") or "professional"
        email_length = campaign_config.get("email_length") or "medium"
        goal = campaign_config.get("goal") or "book a quick review call"
        target_service = campaign_config.get("target_service") or "digital audit services"
        
        sender = sender_profile or {}
        sender_name = sender.get("sender_name", os.getenv("DEFAULT_SENDER_NAME", "Aman Kar"))
        sender_role = sender.get("sender_role", "Outreach Consultant")
        sender_company = sender.get("sender_company", "LeadPilot AI")
        sender_website = sender.get("sender_website", "leadpilot.ai")

        # Formulate instruction prompt
        prompt = f"""
You are an expert B2B Copywriter. Write a highly personalized, conversion-optimized cold email to a prospective lead.
Target Lead Details:
- Business Name: {lead_name}
- Website: {website}
- Industry Category: {category}
- Location: {location}
{f"Technical Website Audit Facts (Use these directly, do NOT invent facts): {audit_details}" if audit_details else "- No specific technical website audit is available. Focus on organic discoverability, visibility, or online customer enquiry flow."}

Campaign Settings:
- Tone of Email: {tone} (professional, friendly, direct, premium agency, short and crisp)
- Target Length: {email_length} (short, medium, detailed)
- Call to Action Goal: {goal}
- Service We Are Pitching: {target_service}

Sender Settings:
- Sender Name: {sender_name}
- Sender Role: {sender_role}
- Sender Company: {sender_company}
- Sender Website: {sender_website}

CRITICAL RULES:
1. Do NOT write generic or spammy-sounding copy.
2. Avoid claiming that we analyzed something if no technical audit facts are listed above. If no audit exists, write a safe, friendly outreach introducing our local services.
3. Word count guidelines:
   - short: 50-80 words
   - medium: 90-140 words
   - detailed: 150-200 words
4. Never make fake promises, guarantee 10x traffic, or list fake statistics.
5. End the email body with a clean signature block using the Sender Settings:
   Best regards,
   [Sender Name]
   [Sender Role] | [Sender Company]
   [Sender Website]

Output your response strictly as a JSON object with these keys:
- subject: a catchy, clickable, non-spammy subject line
- opening_line: a personalized, direct first sentence showing we know their business
- body: the complete cold email body (including salutation, opening_line, value pitch, call to action, and signature)
- cta: the specific Call to Action text used
- personalization_reason: a 1-sentence explanation of why this email is tailored to this lead
- confidence_score: a float between 0.0 and 1.0 representing how personalized this email is (use 0.8+ only if specific technical facts are included, otherwise 0.5-0.6)
- followups: a list of exactly 3 sequential follow-up dicts. Each must have these keys:
  * followup_number: 1, 2, or 3
  * subject: followup subject line (typically 'Re: [Original Subject]')
  * body: followup body text (simple, polite, keeping the chain context, with signature)
  * scheduled_after_days: integer delay days (typically 3 for followup 1, 7 for followup 2, 14 for followup 3)
"""

        # Generate JSON using AIClient
        result = self.ai.generate_json(prompt)
        
        # Validate result keys or use robust fallback
        if "error" in result or not result.get("subject") or not result.get("body"):
            logger.warning(f"AI generation failed or was incomplete. Using fallback template for {lead_name}.")
            result = self._get_fallback_draft(lead_name, category, website, sender_name, sender_role, sender_company, sender_website, target_service, goal)

        return result

    def generate_followups(self, lead: dict, email_draft: dict, campaign_config: dict) -> list[dict]:
        """
        Generates 3 follow-ups explicitly for an existing draft if needed.
        Normally generated inline, but this is a separate utility.
        """
        lead_name = lead.get("business_name") or "Business Owner"
        orig_subject = email_draft.get("subject", "Connecting")
        orig_body = email_draft.get("body", "")

        prompt = f"""
Generate a sequence of 3 simple, polite cold B2B email follow-ups following this email:
Original Subject: {orig_subject}
Original Body: {orig_body}

Follow-up Guidelines:
- Follow-up 1: Simple reminder, ask if they saw the previous email.
- Follow-up 2: Add a small value hint (e.g. standard industry challenge).
- Follow-up 3: Polite break-up email (final attempt).

Output as a JSON array of exactly 3 objects under a "followups" key:
{{
  "followups": [
    {{
      "followup_number": 1,
      "subject": "Re: {orig_subject}",
      "body": "...",
      "scheduled_after_days": 3
    }},
    ...
  ]
}}
"""
        res = self.ai.generate_json(prompt)
        if "error" in res or "followups" not in res:
            return [
                {
                    "followup_number": 1,
                    "subject": f"Re: {orig_subject}",
                    "body": f"Hi,\n\nI wanted to follow up briefly on my previous email. I know how busy your schedule is as a business owner. Just wanted to see if you had 5 minutes for a quick chat next week?\n\nBest,\n{campaign_config.get('sender_name', 'Aman')}",
                    "scheduled_after_days": 3
                },
                {
                    "followup_number": 2,
                    "subject": f"Re: {orig_subject}",
                    "body": f"Hi,\n\nJust checking in to make sure my previous note didn't get buried. We specialize in helping businesses like yours automate their customer acquisition pipelines.\n\nLet me know if you are open to a quick call.\n\nBest,\n{campaign_config.get('sender_name', 'Aman')}",
                    "scheduled_after_days": 7
                },
                {
                    "followup_number": 3,
                    "subject": f"Re: {orig_subject}",
                    "body": f"Hi,\n\nI promise this is the last time I'll occupy your inbox. If customer acquisition isn't a priority for your team right now, I completely understand.\n\nIf you ever need help in the future, please feel free to reach out.\n\nBest,\n{campaign_config.get('sender_name', 'Aman')}",
                    "scheduled_after_days": 14
                }
            ]
        return res["followups"]

    def regenerate_email(self, draft_id: str, instructions: str = None) -> dict:
        """
        Regenerate a specific draft based on user-supplied instructions (e.g. 'Make it shorter').
        """
        db = SessionLocal()
        try:
            from modules.database.models import MailForgeDraft
            draft = db.query(MailForgeDraft).filter(MailForgeDraft.id == draft_id).first()
            if not draft:
                return {"error": "Draft not found"}

            lead_name = "Business Owner"
            if draft.lead_id:
                lead_obj = db.query(Lead).filter(Lead.id == draft.lead_id).first()
                if lead_obj:
                    lead_name = lead_obj.business_name

            prompt = f"""
You are an expert copywriter. Regenerate this cold email draft:
Subject: {draft.subject}
Body: {draft.body}

User Modification Instructions: {instructions or 'Make it more persuasive and clean.'}

Output strictly as a JSON object with:
- subject: new subject line
- body: new email body (including signature)
- opening_line: new opening line
- cta: new cta
- personalization_reason: new personalization reason
- confidence_score: float between 0.0 and 1.0
"""
            result = self.ai.generate_json(prompt)
            if "error" in result:
                return {"error": f"Failed to regenerate: {result['error']}"}
            
            return result
        finally:
            db.close()

    def _get_fallback_draft(self, name, category, website, sender_name, sender_role, sender_company, sender_website, service, goal) -> dict:
        subject = f"Optimizing organic discovery for {name}"
        opening = f"I recently came across {name} online and loved your work in the local {category} sector."
        body = f"""Hi,

{opening}

I noticed your team might be missing out on a few local discovery opportunities due to how the online customer flow and mobile booking path are configured on {website}. 

We specialize in setting up custom, high-converting pipelines and {service} to help local businesses capture active local customers automatically.

Our goal is simple: to make sure you never miss a client who is trying to contact you or book your services today.

Would you be open to a quick 5-minute review next week to see how this could work for {name}?

Best regards,

{sender_name}
{sender_role} | {sender_company}
{sender_website}"""

        return {
            "subject": subject,
            "opening_line": opening,
            "body": body,
            "cta": f"Are you open to a {goal}?",
            "personalization_reason": "Fallback template based on industry segment and website presence.",
            "confidence_score": 0.5,
            "followups": [
                {
                    "followup_number": 1,
                    "subject": f"Re: {subject}",
                    "body": f"Hi,\n\nJust following up on my previous note. I know you're busy running {name}. I'd love to share 2 simple ways to optimize your online inquiries.\n\nAre you open to a brief chat next week?\n\nBest regards,\n\n{sender_name}\n{sender_role} | {sender_company}",
                    "scheduled_after_days": 3
                },
                {
                    "followup_number": 2,
                    "subject": f"Re: {subject}",
                    "body": f"Hi,\n\nChecking in once more. We've helped similar businesses in the {category} space capture up to 30% more online leads just by simplifying their booking layout.\n\nLet me know if you'd be open to a 5-minute call.\n\nBest regards,\n\n{sender_name}\n{sender_role} | {sender_company}",
                    "scheduled_after_days": 7
                },
                {
                    "followup_number": 3,
                    "subject": f"Re: {subject}",
                    "body": f"Hi,\n\nI appreciate that you might be busy, so this will be my final follow-up. If streamlining your customer pipeline isn't a priority for {name} right now, no problem at all.\n\nShould you ever need assistance in the future, feel free to reach out.\n\nBest regards,\n\n{sender_name}\n{sender_role} | {sender_company}",
                    "scheduled_after_days": 14
                }
            ]
        }
