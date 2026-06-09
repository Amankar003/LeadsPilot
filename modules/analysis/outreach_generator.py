"""
outreach_generator.py
Generates personalized, context-aware sales outreach using real audit findings.
Implements the Audit Interpretation and Summarization layers for high-quality B2B copy.
"""
import json
import random
import re
from config import settings
from modules.ai.ai_client import AIClient
from modules.ai.prompts import (
    SYSTEM_PROMPT,
    AUDIT_INTERPRETATION_PROMPT,
    AUDIT_SUMMARIZATION_PROMPT,
    EMAIL_GENERATOR_PROMPT,
    CTA_VARIATIONS,
    FOLLOWUP_GENERATOR_PROMPT
)
from utils.logging_utils import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────
# Modifier Prompts (quick edit actions)
# ─────────────────────────────────────────────
MODIFIER_PROMPTS = {
    "make_shorter": "Rewrite the following email to be shorter. Keep the core message, remove filler. Return JSON: {{\"email_body\": \"\"}}",
    "make_professional": "Rewrite the following email in a formal, professional tone. No casual language. Return JSON: {{\"email_body\": \"\"}}",
    "make_friendly": "Rewrite the following email in a warm, friendly, conversational tone. Return JSON: {{\"email_body\": \"\"}}",
    "stronger_cta": "Add a stronger, clearer call-to-action to the end of this email. Make it easy to say yes. Return JSON: {{\"email_body\": \"\"}}"
}

def clean_business_name(name: str) -> str:
    """Removes platform and source noise suffixes from business name."""
    if not name:
        return ""
    name = name.strip()
    name = re.sub(r'\s+-\s+.*Portal$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+Portal$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*\|.*$', '', name)
    name = re.sub(r'\s+-\s+.*$', '', name)
    return name.strip()

def count_words(text: str) -> int:
    """Helper to count words in a string."""
    if not text:
        return 0
    return len(text.strip().split())

def is_invalid_category(category: str) -> bool:
    """Checks if raw category is actually a raw search query / invalid text."""
    if not category:
        return True
    c_lower = category.lower()
    invalid_patterns = [
        "site:", "@gmail.com", "@", '"', "'", "inurl:", "intitle:", 
        "filetype:", " or ", " and ", "+", "ext:", "link:"
    ]
    for pat in invalid_patterns:
        if pat in c_lower:
            return True
    if len(category.split()) > 4 and ("google" in c_lower or "search" in c_lower or ".com" in c_lower):
        return True
    return False

def infer_category(business_name: str, raw_category: str) -> str:
    """Safely infers a clean category from business name or valid category."""
    if raw_category and not is_invalid_category(raw_category):
        return raw_category.strip()
    name_lower = (business_name or "").lower()
    if "creative arts" in name_lower:
        return "creative arts education"
    elif "school" in name_lower or "academy" in name_lower or "college" in name_lower:
        return "education"
    elif "hotel" in name_lower or "inn" in name_lower or "resort" in name_lower:
        return "hospitality"
    elif "clinic" in name_lower or "dental" in name_lower or "dentist" in name_lower or "medical" in name_lower:
        return "healthcare"
    elif "restaurant" in name_lower or "cafe" in name_lower or "bistro" in name_lower or "kitchen" in name_lower:
        return "food and beverage"
    elif "salon" in name_lower or "spa" in name_lower or "beauty" in name_lower:
        return "personal care services"
    elif "plumbing" in name_lower or "electric" in name_lower or "hvac" in name_lower or "roof" in name_lower:
        return "home improvement services"
    return "local service business"

def generate_outreach(report, lead, email_type: str, tone: str, length: str, cta_goal: str, service_focus: str) -> dict:
    """
    Generate personalized, human-sounding outreach based on full lead + audit context.
    Executes a 3-stage interpretation, summarization, and generation pipeline.
    """
    ai = AIClient()

    # 1. Prepare raw data
    raw_lead_name = lead.business_name or "Unknown"
    cleaned_lead_name = clean_business_name(raw_lead_name)
    raw_category = lead.category or "Unknown"
    inferred_category = infer_category(cleaned_lead_name, raw_category)
    city = f"{lead.city or ''}, {lead.state or ''}".strip(", ") or lead.address or "Unknown"
    
    logger.info("--- OUTREACH GENERATION DEBUG START ---")
    logger.info(f"Cleaned Lead Name: {cleaned_lead_name}")
    logger.info(f"Inferred Category: {inferred_category}")
    
    raw_audit = report.raw_audit_json or {} if report else {}
    # Convert raw audit to a dense summary to fit in prompt limits easily
    raw_audit_text = json.dumps(raw_audit, indent=2)[:3000] if raw_audit else "No technical audit available."
    
    # =========================================================================
    # STAGE 1: Audit Interpretation Layer
    # =========================================================================
    interp_prompt = AUDIT_INTERPRETATION_PROMPT.format(
        raw_audit_data=raw_audit_text,
        industry=inferred_category,
        location=city
    )
    logger.info(f"Running Audit Interpretation Stage for {cleaned_lead_name}")
    interp_result = ai.generate_json(interp_prompt, system_prompt=SYSTEM_PROMPT, task_name="audit_generation")
    interpreted_opps = json.dumps(interp_result.get("interpreted_opportunities", []), indent=2)
    
    # =========================================================================
    # STAGE 2: Audit Summarization Layer
    # =========================================================================
    summ_prompt = AUDIT_SUMMARIZATION_PROMPT.format(
        company_name=cleaned_lead_name,
        industry=inferred_category,
        location=city,
        interpreted_opportunities=interpreted_opps
    )
    logger.info(f"Running Audit Summarization Stage for {cleaned_lead_name}")
    summ_result = ai.generate_json(summ_prompt, system_prompt=SYSTEM_PROMPT, task_name="audit_generation")
    audit_summary = json.dumps(summ_result, indent=2)
    
    # =========================================================================
    # STAGE 3: Personalization & Variation Rules
    # =========================================================================
    # Deterministic rotation based on lead id to ensure variety across a campaign
    lead_id = getattr(lead, 'id', random.randint(1, 100))
    if isinstance(lead_id, str):
        # Convert first 8 hex characters of UUID to an integer for modulo operations
        hash_val = int(lead_id.replace('-', '')[:8], 16)
    else:
        hash_val = lead_id

    selected_cta = CTA_VARIATIONS[hash_val % len(CTA_VARIATIONS)]
    
    # =========================================================================
    # STAGE 4: Email Generation
    # =========================================================================
    ai_report_json = getattr(report, "ai_report_json", {}) or {}
    executive_report = ai_report_json.get("executive_summary", "No executive summary available.")
    pain_points = json.dumps(ai_report_json.get("top_pain_points", getattr(report, "pain_points_json", []) or []), indent=2)
    recommended_services = json.dumps(ai_report_json.get("recommended_services", getattr(report, "recommended_services_json", []) or []), indent=2)

    gen_prompt = EMAIL_GENERATOR_PROMPT.format(
        executive_report=executive_report,
        pain_points=pain_points,
        recommended_services=recommended_services,
        audit_summary=audit_summary,
        sender_name=settings.SENDER_NAME,
        sender_role=settings.SENDER_ROLE,
        agency_website=settings.AGENCY_WEBSITE,
        cta_variation=selected_cta,
        company_name=cleaned_lead_name,
        industry=inferred_category,
        location=city
    )
    logger.info("=" * 60)
    logger.info("DEBUG PHASE 1: VERIFYING EMAIL GENERATION INPUTS")
    logger.info(f"EXECUTIVE REPORT:\n{executive_report}\n")
    logger.info(f"PAIN POINTS:\n{pain_points}\n")
    logger.info(f"RECOMMENDED SERVICES:\n{recommended_services}\n")
    logger.info(f"AUDIT SUMMARY:\n{audit_summary}\n")
    logger.info(f"FINAL PROMPT TO LLM:\n{gen_prompt}\n")
    logger.info("=" * 60)
    
    logger.info(f"Running Email Generation for {cleaned_lead_name}")
    
    # ─── Banned phrase quality gate ───
    BANNED_PHRASES = [
        "I recently reviewed", "We specialize in", "Hope you're doing well",
        "I hope this email finds you well", "5-minute review", "digital setup",
        "services services", "I wanted to reach out", "brief call",
        "book a call", "schedule a meeting", "game-changer", "skyrocket",
        "significant portion", "active local mobile users",
    ]
    
    def _has_banned_phrases(text: str) -> list:
        """Return list of banned phrases found in text."""
        found = []
        lower = text.lower()
        for phrase in BANNED_PHRASES:
            if phrase.lower() in lower:
                found.append(phrase)
        # Also flag "your business" repeated 3+ times
        if lower.count("your business") >= 3:
            found.append("your business (repeated)")
        return found
    
    def _sanitize_email(text: str) -> str:
        """Remove banned phrases from the email as a last resort."""
        for phrase in BANNED_PHRASES:
            text = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE)
        # Collapse double spaces and blank lines left behind
        text = re.sub(r'  +', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
    
    max_attempts = 2
    final_result = {}
    for attempt in range(max_attempts):
        final_result = ai.generate_json(gen_prompt, system_prompt=SYSTEM_PROMPT, task_name="email_generation")
        email_body = final_result.get("email_body", "")

        word_count = len(email_body.split())
        has_bullets = any(marker in email_body for marker in ["•", "*", "—", "-"])
        has_business_name = cleaned_lead_name.lower() in email_body.lower() if cleaned_lead_name else True
        banned_found = _has_banned_phrases(email_body)
        
        if word_count >= 100 and has_bullets and has_business_name and not banned_found:
            logger.info("Email generation passed validation checks.")
            break
        else:
            reasons = []
            if word_count < 100:
                reasons.append(f"too_short={word_count}")
            if not has_bullets:
                reasons.append("no_bullets")
            if not has_business_name:
                reasons.append("missing_business_name")
            if banned_found:
                reasons.append(f"banned={banned_found}")
            logger.warning(f"Email validation failed (Attempt {attempt + 1}/{max_attempts}): {', '.join(reasons)}")
    
    # Final sanitization pass — clean any remaining banned phrases
    email_body = final_result.get("email_body", "")
    if _has_banned_phrases(email_body):
        logger.info("Running fallback sanitizer to remove banned phrases.")
        email_body = _sanitize_email(email_body)
        final_result["email_body"] = email_body
    
    # Ensure signature is perfectly appended and clean up LLM hallucinations
    email_body = final_result.get("email_body", "")
    
    # Strip hallucinated generic signatures
    for term in ["Best regards,", "Best regards", "Best,", "Warm regards,", "Warm regards", "Sincerely,", "Sincerely", "Regards,", "Regards"]:
        if term in email_body:
            idx = email_body.rfind(term)
            email_body = email_body[:idx].strip()
            break

    # Add correct signature block
    sig_text = f"\n\nBest regards,\n\n{settings.SENDER_NAME}\n{settings.SENDER_ROLE}\n3Fi Tech\n{settings.AGENCY_WEBSITE}"
    email_body = email_body.strip() + sig_text
    
    final_result["email_body"] = email_body
    
    # Match UI expectations for subject lines array
    if "subject" in final_result and "subject_lines" not in final_result:
        final_result["subject_lines"] = [final_result["subject"]]
    elif "subject_lines" not in final_result:
        final_result["subject_lines"] = ["Growth ideas for your team"]
        
    word_count = count_words(email_body.split("\n\nBest regards,")[0])
    final_result["word_count"] = word_count
    
    logger.info(f"Final Word Count (core): {word_count}")
    logger.info("--- OUTREACH GENERATION DEBUG END ---")
    
    return final_result


def apply_modifier(current_email_body: str, modifier: str) -> str:
    """Quick-edit the existing email body using a modifier action."""
    ai = AIClient()
    base_prompt = MODIFIER_PROMPTS.get(modifier, "")
    if not base_prompt:
        return current_email_body

    prompt = f"{base_prompt}\n\nEMAIL:\n{current_email_body}"
    result = ai.generate_json(prompt, task_name="email_generation")

    if "error" in result:
        logger.error(f"Modifier '{modifier}' failed: {result.get('error')}")
        return current_email_body

    return result.get("email_body", current_email_body)



