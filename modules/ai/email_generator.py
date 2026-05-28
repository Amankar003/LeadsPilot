import json
import os
from modules.ai.ai_client import AIClient
from modules.ai.prompts import EMAIL_GENERATOR_PROMPT, FOLLOWUP_GENERATOR_PROMPT

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
        import re
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
        # In a real system, you would scrape/analyze the website here. For now, use minimal facts.
        audit_data = {
            "business_name": business_name,
            "website": website,
            "email": email
        }
        pain_points = []  # Could be filled by a real analyzer
        services = []     # Could be filled by a real recommender
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
            # Fallback to generic draft
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

        # Formulate lead details matching our standard structure
        lead_data_dict = {
            "business_name": cleaned_name,
            "category": inferred_cat,
            "location": lead_data.get("location", "Unknown"),
            "website": lead_data.get("website", "No website found"),
            "rating": lead_data.get("rating", "N/A"),
            "reviews": lead_data.get("reviews", "N/A"),
            "phone": lead_data.get("phone", "N/A"),
            "email": lead_data.get("email", "N/A")
        }

        # Fallback Mode is naturally active since no intelligence analysis report is provided directly
        lead_analysis_text = "[NO LEAD INTELLIGENCE AND ANALYSIS AVAILABLE - FALLBACK OUTREACH MODE IS ACTIVE]\n\n" \
                             "Since no technical audit or intelligence is available, you must write a safe general outreach email based ONLY on the available RAW LEAD DATA.\n" \
                             "Do NOT invent any technical problems, poor mobile/SEO experience, or speed issues.\n\n" \
                             "Use one of the following safe fallback angles depending on the lead category and raw data:\n" \
                             "- If the website is missing: Pitch a clean, professional website and a seamless online enquiry flow.\n" \
                             "- If rating/reviews are available (e.g. high rating): Focus on leveraging their existing trust and local reputation to capture even more digital enquiries.\n" \
                             "- If school/college: Focus on admission enquiry handling, parent communication, and website usability.\n" \
                             "- If clinic/hospital: Focus on appointment enquiry handling, patient trust, and seamless booking.\n" \
                             "- If restaurant/cafe: Focus on online bookings, order enquiry flow, and guest experience.\n" \
                             "- If salon/spa: Focus on appointment booking, local visibility, and repeat customer follow-ups.\n" \
                             "- If only name/category/location are available: Focus on general digital discoverability and enquiry handling."

        sender_info = sender or {}
        sender_name = sender_info.get("sender_name", os.getenv("SENDER_NAME", "Deepak Kishor"))
        sender_role = sender_info.get("sender_role", os.getenv("SENDER_ROLE", "Founder & Lead Strategist"))
        agency_website = sender_info.get("agency_website", os.getenv("AGENCY_WEBSITE", "3fitech.com"))

        prompt = EMAIL_GENERATOR_PROMPT.format(
            lead_data=json.dumps(lead_data_dict, indent=2, ensure_ascii=False),
            lead_analysis=lead_analysis_text,
            sender_name=sender_name,
            sender_role=sender_role,
            agency_website=agency_website
        )

        result = self.ai.generate_json(prompt)
        
        email_body = result.get("email_body", "")
        def count_words(text):
            if not text: return 0
            return len(text.strip().split())
            
        # Retry once if word count is under 90 words or above 180 words
        word_count = count_words(email_body)
        if word_count < 90 or word_count > 180:
            retry_prompt = prompt + "\n\n========================\nSTRICT RE-GENERATION REQUIREMENT\n========================\n" \
                                    "Rewrite this B2B email to be highly professional and structured, containing exactly 120 to 160 words in 3 distinct paragraphs."
            retry_result = self.ai.generate_json(retry_prompt)
            if "error" not in retry_result:
                result = retry_result
                email_body = result.get("email_body", "")
                word_count = count_words(email_body)

        # Smart fallback template if still not within target bounds or failing
        if "error" in result or word_count < 90:
            deterministic_body = (
                f"I came across {lead_data_dict['business_name']} and noticed a couple of areas that could be improved online. Specifically, the current setup could benefit from stronger trust signals, such as visible testimonials, and a clearer enquiry-focused page for people who want to contact or book quickly.\n\n"
                f"For a local {lead_data_dict['category']} business, these small gaps can make it harder for new visitors to understand your value, trust your service, and reach out immediately.\n\n"
                f"At 3FI Tech, we specialize in helping local businesses with exactly this — building a conversion-focused landing page, stronger enquiry CTAs, testimonial sections, and WhatsApp integration. Would you be open to a quick 5-minute review next week to see how this could work for {lead_data_dict['business_name']}?"
            )
            result["email_body"] = deterministic_body
            email_body = deterministic_body
            
        # Clean whitespace and leading indents from email_body lines
        if "email_body" in result and result["email_body"]:
            cleaned_lines = [line.strip() for line in result["email_body"].split("\n")]
            result["email_body"] = "\n".join(cleaned_lines)

        # Ensure a beautifully structured vertical B2B signature stack is present
        if "email_body" in result and result["email_body"]:
            body_text = result["email_body"].strip()
            
            # Clean any trailing partial/inline signatures or company mentions that LLM might have written
            for term in ["Best regards,", "Best regards", "Best,", "Warm regards,", "Warm regards", "Sincerely,", "Sincerely", "Regards,", "Regards"]:
                if body_text.endswith(term):
                    body_text = body_text[:-len(term)].strip()
                    break
            
            # If it generated a messy inline signature line, strip it
            if "Best regards, " in body_text:
                idx = body_text.rfind("Best regards, ")
                body_text = body_text[:idx].strip()
            elif "Best regards" in body_text:
                idx = body_text.rfind("Best regards")
                body_text = body_text[:idx].strip()
                
            sig_text = f"\n\nBest regards,\n\n{sender_name}\n{sender_role}\n3FI Tech\n{agency_website}"
            result["email_body"] = body_text + sig_text

        # Ensure subject and other expected keys are filled
        if "error" in result:
            return {
                "error": result.get("error"), 
                "subject": "Digital Partnership Idea", 
                "email_body": "Dear Business Owner,\n\nWe would love to help you with Digital Development.\n\nBest,\n3FI Tech Team"
            }

        return result

    def generate_followup(self, lead_data: dict, original_subject: str, original_body: str, followup_number: int) -> dict:
        """
        Generate follow-up email.
        Used by legacy and migration utilities.
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

        result = self.ai.generate_json(prompt)
        if "error" in result:
            # Fallback
            if followup_number == 1:
                return {
                    "subject": f"Re: {original_subject}",
                    "body": f"Hi,\n\nI wanted to follow up on my previous email regarding some digital improvement ideas for {lead_details['business_name']}. I know you're busy, but I'd love to share 2-3 specific ways you can increase your enquiries.\n\nWould you be open to a quick 5-minute chat next week?\n\nBest regards,\n{os.getenv('SENDER_NAME', 'Aman Kar')}"
                }
            else:
                return {
                    "subject": f"Re: {original_subject}",
                    "body": f"Hi,\n\nJust sending a quick final follow-up. If you're not the right person or if this isn't a priority for {lead_details['business_name']} right now, no worries at all.\n\nBest,\n{os.getenv('SENDER_NAME', 'Aman Kar')}"
                }

        return result
