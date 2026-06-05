import json
import os
import re
import random
from modules.ai.ai_client import AIClient
from modules.ai.prompts import (
    SYSTEM_PROMPT,
    EMAIL_GENERATOR_PROMPT,
    FOLLOWUP_GENERATOR_PROMPT,
    EMAIL_STYLES,
    CTA_VARIATIONS,
    ANTI_SPAM_RULES
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
                "subject": outreach.get("email_subject", "Let's Connect"),
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

        # Randomize style for draft
        style_keys = list(EMAIL_STYLES.keys())
        selected_style = EMAIL_STYLES[random.choice(style_keys)]
        selected_cta = random.choice(CTA_VARIATIONS)

        prompt = EMAIL_GENERATOR_PROMPT.format(
            executive_report="Initial AI review suggests significant digital gaps.",
            pain_points=json.dumps([{"title": "Weak Digital Presence", "severity": "medium", "evidence": "Low local search visibility"}]),
            recommended_services=json.dumps([{"service_name": "Digital Marketing", "priority": "High"}]),
            audit_summary=audit_summary,
            sender_name=sender_name,
            sender_role=sender_role,
            agency_website=agency_website,
            email_style_name=selected_style["name"],
            email_style_tone=selected_style["tone"],
            email_style_opening=selected_style["opening_pattern"],
            cta_variation=selected_cta,
            anti_spam_rules=ANTI_SPAM_RULES
        )

        result = self.ai.generate_json(prompt, system_prompt=SYSTEM_PROMPT)
        
        email_body = result.get("email_body", "")
        def count_words(text):
            if not text: return 0
            return len(text.strip().split())
            
        word_count = count_words(email_body)
        
        if "error" in result or word_count < 90:
            deterministic_body = (
                f"I was researching {inferred_cat} providers in {location} and took a closer look at {cleaned_name}'s online presence.\n\n"
                f"I put together a few quick observations that could help capture more enquiries:\n"
                f"• Digital discoverability could be improved to capture local search traffic.\n"
                f"• Enquiry pathways currently have some friction for mobile visitors.\n\n"
                f"For a local business, these small gaps can lead to missing inbound leads and lower conversion rates on first impressions.\n\n"
                f"✓ Digital discoverability → Enhance local search signals\n"
                f"✓ Enquiry pathways → Implement simpler contact flows like WhatsApp\n\n"
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
                
            sig_text = f"\n\nBest regards,\n\n{sender_name}\n{sender_role}\n3FI Tech\n{agency_website}"
            result["email_body"] = body_text + sig_text

        if "error" in result:
            return {
                "error": result.get("error"), 
                "subject": "Digital Partnership Idea", 
                "email_body": result.get("email_body", "Dear Business Owner,\n\nWe would love to help you with Digital Development.\n\nBest,\n3FI Tech Team")
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

        result = self.ai.generate_json(prompt, system_prompt=SYSTEM_PROMPT)
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
