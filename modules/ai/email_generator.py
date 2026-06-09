import json
import os
import re
import random
from modules.ai.ai_client import AIClient
from modules.ai.prompts import (
    SYSTEM_PROMPT,
    EMAIL_GENERATOR_PROMPT,
    FOLLOWUP_GENERATOR_PROMPT,
    CTA_VARIATIONS
)
from config import settings

class EmailGenerator:
    """
    Service class wrapping AI email and follow-up generation.
    Maintains compatibility with tests and UI pages.
    """
    def __init__(self):
        self.ai = AIClient()

    def generate_from_email_only(self, email: str, sender: dict = None) -> dict:
        """
        Given only an email address, infer business name, website, receiver name, analyze the website for bugs, and generate a custom outreach email.
        """
        from modules.analysis.outreach_generator import clean_business_name, infer_category
        from modules.analysis.ai_report_generator import generate_ai_report

        # 1. Parse domain and guess website
        match = re.match(r"^[^@]+@([\w.-]+)$", email)
        domain = match.group(1) if match else None
        website = f"https://{domain}" if domain else "No website found"

        # 2. Guess business name from domain (strip TLD, dashes, etc.)
        business_name_guess = domain.split(".")[0].replace("-", " ").title() if domain else "Unknown"
        business_name = clean_business_name(business_name_guess)

        # 3. Guess receiver name from email prefix (optional, fallback to generic)
        prefix = email.split("@")[0]
        receiver_name = prefix.replace(".", " ").replace("_", " ").title()
        if receiver_name in ["Info", "Contact", "Admin", "Support"]:
            receiver_name = "Business Owner"

        # 4. Prepare minimal lead data for analysis
        lead_data = {
            "business_name": business_name,
            "website": website,
            "email": email,
            "name": receiver_name,
            "category": infer_category(business_name, None),
            "location": "Unknown"
        }

        # 5. Run AI audit/analysis (simulate minimal audit facts for now)
        audit_data = {
            "business_name": business_name,
            "website": website,
            "email": email
        }
        pain_points = []
        services = []
        ai_report = generate_ai_report(audit_data, pain_points, services)

        # 6. Generate outreach email using the AI report (fallback to draft if error)
        if "error" not in ai_report:
            outreach = ai_report.get("outreach", {})
            return {
                "subject": outreach.get("subject", "Let's Connect"),
                "email_body": outreach.get("email_body", ""),
                "business_name": business_name,
                "receiver_name": receiver_name,
                "website": website,
                "ai_report": ai_report
            }
        else:
            return self.generate_draft(lead_data, sender)

    def generate_draft(self, lead_data: dict, sender: dict = None) -> dict:
        """
        Generate email draft from raw lead data. 
        Highly compatible with scratch/test_fixes.py.
        """
        from modules.analysis.outreach_generator import clean_business_name, infer_category
        
        raw_name = lead_data.get("name", lead_data.get("business_name", "Unknown"))
        cleaned_name = clean_business_name(raw_name)
        raw_category = lead_data.get("category", "Unknown")
        inferred_cat = infer_category(cleaned_name, raw_category)
        location = lead_data.get("location", "Unknown")

        # Fake an audit summary since we don't have real intelligence
        audit_summary = json.dumps({
            "company_name": cleaned_name,
            "industry": inferred_cat,
            "location": location,
            "top_opportunities": [
                "Digital discoverability and visibility",
                "Streamlining customer enquiry pathways"
            ],
            "potential_business_impacts": [
                "Missing inbound leads from mobile users",
                "Lower conversion rates on first impressions"
            ],
            "recommended_improvements": [
                {"observation": "Digital discoverability could be improved", "recommendation": "Enhance local search signals"},
                {"observation": "Enquiry pathways have friction", "recommendation": "Implement simpler contact flows like WhatsApp"}
            ],
            "relevant_services": ["Local SEO", "Lead Capture Systems"]
        }, indent=2)

        sender_info = sender or {}
        sender_name = sender_info.get("sender_name", settings.SENDER_NAME)
        sender_role = sender_info.get("sender_role", settings.SENDER_ROLE)
        agency_website = sender_info.get("agency_website", settings.AGENCY_WEBSITE)

        # Select CTA
        selected_cta = random.choice(CTA_VARIATIONS)

        prompt = EMAIL_GENERATOR_PROMPT.format(
            executive_report="Initial AI review suggests digital gaps that may be limiting inbound enquiries.",
            pain_points=json.dumps([{"title": "Weak Local Visibility", "severity": "medium", "evidence": "Low local search presence"}]),
            recommended_services=json.dumps([{"service_name": "Local SEO & Lead Capture", "priority": "High"}]),
            audit_summary=audit_summary,
            sender_name=sender_name,
            sender_role=sender_role,
            agency_website=agency_website,
            cta_variation=selected_cta,
            company_name=cleaned_name,
            industry=inferred_cat,
            location=location
        )

        result = self.ai.generate_json(prompt, system_prompt=SYSTEM_PROMPT, task_name="email_generation")
        
        email_body = result.get("email_body", "")
        def count_words(text):
            if not text: return 0
            return len(text.strip().split())
            
        word_count = count_words(email_body)
        
        if "error" in result or word_count < 90:
            deterministic_body = (
                f"Hi {cleaned_name} team,\n\n"
                f"While looking at {inferred_cat} businesses in {location}, I noticed a few areas where {cleaned_name} could turn more website visitors into direct enquiries.\n\n"
                f"For {inferred_cat} businesses, many potential customers visit from mobile while deciding where to go. "
                f"If the next step is not immediately clear, those visitors may leave without contacting the business.\n\n"
                f"A few practical improvements could help:\n\n"
                f"* Add clearer enquiry and contact paths \u2014 so visitors know exactly how to reach you.\n"
                f"* Improve mobile call and direction buttons \u2014 so nearby customers can act quickly.\n"
                f"* Highlight reviews and trust signals \u2014 so first-time visitors feel more confident.\n"
                f"* Add simple follow-up automation \u2014 so enquiries are not missed during busy hours.\n\n"
                f"At 3Fi Tech, we help service businesses improve local visibility, website journeys, lead capture, and follow-up systems so more visitors turn into real enquiries.\n\n"
                f"{selected_cta}"
            )
            result["email_body"] = deterministic_body
            email_body = deterministic_body
            
        if "email_body" in result and result["email_body"]:
            cleaned_lines = [line.strip() for line in result["email_body"].split("\n")]
            result["email_body"] = "\n".join(cleaned_lines)

        if "email_body" in result and result["email_body"]:
            body_text = result["email_body"].strip()
            
            for term in ["Best regards,", "Best regards", "Best,", "Warm regards,", "Warm regards", "Sincerely,", "Sincerely", "Regards,", "Regards"]:
                if body_text.endswith(term):
                    body_text = body_text[:-len(term)].strip()
                    break
            
            if "Best regards, " in body_text:
                idx = body_text.rfind("Best regards, ")
                body_text = body_text[:idx].strip()
            elif "Best regards" in body_text:
                idx = body_text.rfind("Best regards")
                body_text = body_text[:idx].strip()
                
            sig_text = f"\n\nBest regards,\n\n{sender_name}\n{sender_role}\n3Fi Tech\n{agency_website}"
            result["email_body"] = body_text + sig_text

        if "error" in result:
            return {
                "error": result.get("error"), 
                "subject": "Digital Partnership Idea", 
                "email_body": result.get("email_body", f"Hi there,\n\nWe noticed a few areas where your online presence could bring in more enquiries. At 3Fi Tech, we help service businesses improve local visibility and lead capture.\n\nWould it be useful if we shared a complimentary audit report?\n\nBest regards,\n{settings.SENDER_NAME}")
            }

        return result

    def generate_followup(self, lead_data: dict, original_subject: str, original_body: str, followup_number: int) -> dict:
        """
        Generate follow-up email.
        """
        lead_details = {
            "business_name": lead_data.get("business_name", lead_data.get("name", "Unknown")),
            "category": lead_data.get("category", "Unknown"),
            "location": lead_data.get("location", "Unknown"),
            "website": lead_data.get("website", "No website found")
        }

        prompt = FOLLOWUP_GENERATOR_PROMPT.format(
            lead_details=json.dumps(lead_details, indent=2, ensure_ascii=False),
            original_subject=original_subject,
            original_body=original_body,
            followup_number=followup_number
        )

        result = self.ai.generate_json(prompt, system_prompt=SYSTEM_PROMPT, task_name="email_generation")
        if "error" in result:
            if followup_number == 1:
                return {
                    "subject": f"Re: {original_subject}",
                    "body": f"Hi,\n\nI wanted to follow up on my previous email regarding some digital improvement ideas for {lead_details['business_name']}. I know you're busy, but I'd love to share 2-3 specific ways you can increase your enquiries.\n\nWould you be open to a quick 5-minute chat next week?\n\nBest regards,\n{settings.SENDER_NAME}"
                }
            else:
                return {
                    "subject": f"Re: {original_subject}",
                    "body": f"Hi,\n\nJust sending a quick final follow-up. If you're not the right person or if this isn't a priority for {lead_details['business_name']} right now, no worries at all.\n\nBest,\n{settings.SENDER_NAME}"
                }

        return result
