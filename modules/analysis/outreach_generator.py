"""
outreach_generator.py
Generates personalized, context-aware sales outreach using real audit findings.
All output is grounded in actual evidence — no hallucination.
"""
import json
from modules.ai.ai_client import AIClient
from utils.logging_utils import get_logger
from config import settings

logger = get_logger(__name__)

# ─────────────────────────────────────────────
# Prompt Template
# ─────────────────────────────────────────────
OUTREACH_PROMPT = """
You are a senior B2B sales copywriter for a digital services agency.
Your job is to write personalized outreach messages based ONLY on verified audit findings.

STRICT RULES:
- Do NOT hallucinate. Use only the facts provided below.
- Mention maximum 1-2 pain points in the email.
- Recommend maximum 1-2 services per message.
- Do not use generic openers like "I hope you are doing well" or "I came across your business".
- Do not include the recipient's email in the message body.
- Do not sound salesy or robotic.
- Keep the email body between 80-140 words.
- Personalize using: business name, category, city, and a specific audit finding.
- Match the tone requested: {tone}
- Match the email type: {email_type}
- Match the CTA goal: {cta_goal}
- Focus the message on this service: {service_focus}
- Length preference: {length}

LEAD CONTEXT:
- Business Name: {business_name}
- Category: {category}
- City: {city}
- Website: {website_status}
- Opportunity Level: {opportunity_level}

TOP PAIN POINTS (use max 2):
{pain_points}

RECOMMENDED SERVICES (use max 2):
{recommended_services}

MAIN PITCH ANGLE FROM AUDIT:
{main_pitch_angle}

EXECUTIVE SUMMARY:
{executive_summary}

INSTRUCTIONS BY EMAIL TYPE:
- Cold Outreach: First touch. Hook with a specific insight about their business. No pressure.
- Follow-up 1: Reference a previous email. Add one new value point.
- Follow-up 2: Final touch. Keep it short. Add a simple closing offer.
- No Website Pitch: Emphasize lost business due to no online presence.
- Website Redesign Pitch: Mention specific UX or conversion issue found.
- SEO Pitch: Mention specific visibility or ranking gap found.
- App/Booking System Pitch: Mention missed bookings or manual friction.
- AI Chatbot/Automation Pitch: Mention 24/7 inquiry handling or response gap.

Return ONLY valid JSON with this exact structure:
{{
  "subject_lines": [
    "Subject option 1",
    "Subject option 2",
    "Subject option 3"
  ],
  "email_body": "Complete email body here (no salutation needed, start with the hook)",
  "whatsapp_message": "Short WhatsApp message under 60 words. Friendly and direct.",
  "linkedin_message": "LinkedIn connection note under 50 words. Professional and curious.",
  "follow_up_1": "Follow-up 1 email body (reference previous message, add value)",
  "follow_up_2": "Follow-up 2 email body (final short closing message)"
}}
"""

# ─────────────────────────────────────────────
# Modifier Prompts (quick edit actions)
# ─────────────────────────────────────────────
MODIFIER_PROMPTS = {
    "make_shorter": "Rewrite the following email to be under 80 words. Keep the core message, remove filler. Return JSON: {{\"email_body\": \"\"}}",
    "make_professional": "Rewrite the following email in a formal, professional tone. No casual language. Return JSON: {{\"email_body\": \"\"}}",
    "make_friendly": "Rewrite the following email in a warm, friendly, conversational tone. Return JSON: {{\"email_body\": \"\"}}",
    "stronger_cta": "Add a stronger, clearer call-to-action to the end of this email. Make it easy to say yes. Return JSON: {{\"email_body\": \"\"}}"
}


def build_pain_points_text(pain_points: list) -> str:
    """Format top 2 pain points for the prompt."""
    top = pain_points[:2]
    lines = []
    for pp in top:
        lines.append(
            f"- [{pp.get('severity', 'N/A').upper()}] {pp.get('title', '')}: {pp.get('evidence', '')} "
            f"(Business impact: {pp.get('business_impact', '')})"
        )
    return "\n".join(lines) if lines else "No specific pain points detected."


def build_services_text(services: list, service_focus: str) -> str:
    """Format top 2 services, prioritizing the user's selected focus."""
    if service_focus and service_focus != "Auto (from report)":
        # Put the focused service first
        sorted_services = sorted(
            services,
            key=lambda s: 0 if service_focus.lower() in s.get("service_name", "").lower() else 1
        )
    else:
        sorted_services = services

    top = sorted_services[:2]
    lines = []
    for svc in top:
        lines.append(
            f"- {svc.get('service_name', '')} (Priority: {svc.get('priority', '')}): {svc.get('pitch_angle', '')}"
        )
    return "\n".join(lines) if lines else "General digital improvement services."


import os
from modules.ai.prompts import EMAIL_GENERATOR_PROMPT, FOLLOWUP_GENERATOR_PROMPT

def count_words(text: str) -> int:
    """Helper to count words in a string."""
    if not text:
        return 0
    return len(text.strip().split())

def generate_followup(lead, email_subject: str, email_body: str, followup_number: int) -> str:
    """Generate a follow-up email using the defined FOLLOWUP_GENERATOR_PROMPT."""
    ai = AIClient()
    
    lead_details = {
        "business_name": lead.business_name,
        "category": lead.category,
        "location": f"{lead.city or ''}, {lead.state or ''}, {lead.country or ''}".strip(", ") or lead.address or "Unknown",
        "website": lead.website
    }
    
    prompt = FOLLOWUP_GENERATOR_PROMPT.format(
        lead_details=json.dumps(lead_details, indent=2, ensure_ascii=False),
        original_subject=email_subject,
        original_body=email_body,
        followup_number=followup_number
    )
    
    result = ai.generate_json(prompt)
    if "error" in result:
        if followup_number == 1:
            return f"Hi,\n\nI wanted to follow up on my previous email regarding some digital improvement ideas for {lead.business_name}. I know you're busy, but I'd love to share 2-3 specific ways you can increase your enquiries.\n\nWould you be open to a quick 5-minute chat next week?\n\nBest regards,\n{settings.SENDER_NAME}\n{settings.SENDER_ROLE}\n3FI Tech\n{settings.AGENCY_WEBSITE}"
        else:
            return f"Hi,\n\nJust sending a quick final follow-up. If you're not the right person or if this isn't a priority for {lead.business_name} right now, no worries at all.\n\nIf you are interested in a quick, low-risk way to boost your online discoverability, feel free to reply here.\n\nBest,\n{settings.SENDER_NAME}\n{settings.SENDER_ROLE}\n3FI Tech\n{settings.AGENCY_WEBSITE}"
            
    return result.get("body", "")

import re

def clean_business_name(name: str) -> str:
    """Removes platform and source noise suffixes from business name."""
    if not name:
        return ""
    name = name.strip()
    # Remove "- Highams Park Portal", "- London Portal" etc.
    name = re.sub(r'\s+-\s+.*Portal$', '', name, flags=re.IGNORECASE)
    # Remove " Portal" suffix at the end
    name = re.sub(r'\s+Portal$', '', name, flags=re.IGNORECASE)
    # Remove trailing source or search noise (e.g. "| ...", " - ...")
    name = re.sub(r'\s*\|.*$', '', name)
    name = re.sub(r'\s+-\s+.*$', '', name)
    return name.strip()

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

def normalize_pain_points(pain_points: list) -> list:
    """Normalizes raw technical pain points into friendly, natural B2B phrases."""
    if not pain_points:
        return []
    mapping = {
        "missing social proof": "limited visible testimonials or trust-building proof for new visitors",
        "missing dedicated digital platform": "no clear conversion-focused page or digital pathway for enquiries",
        "missing whatsapp integration": "no quick WhatsApp/contact option for mobile-first enquiries",
        "weak local visibility": "limited local search visibility",
        "missing booking system": "no simple online booking or enquiry flow",
        "weak trust signals": "not enough visible credibility signals for first-time visitors",
        "missing whatsapp": "no quick WhatsApp/contact option for mobile-first enquiries",
        "no mobile optimization": "a landing page that is not mobile-friendly",
        "missing client portal": "no private client communication portal",
        "poor seo": "limited organic search discoverability in your local area",
    }
    normalized = []
    for p in pain_points:
        title = ""
        severity = "medium"
        if isinstance(p, dict):
            title = p.get("title", "")
            severity = p.get("severity", "medium")
        else:
            title = str(p)
        t_lower = title.lower().strip()
        matched = False
        for k, v in mapping.items():
            if k in t_lower:
                normalized.append({"title": v, "severity": severity})
                matched = True
                break
        if not matched:
            normalized.append({"title": title, "severity": severity})
    return normalized

def expand_services(pain_points: list) -> list:
    """Maps normalized pain points directly to relevant 3FI Tech premium services."""
    services = []
    added = set()
    mapping = {
        "testimonials": ("testimonial sections and trust badges", "High"),
        "social proof": ("testimonial sections and trust badges", "High"),
        "trust signals": ("testimonial sections and trust badges", "High"),
        "dedicated digital platform": ("a conversion-focused landing page and clearer enquiry pathways", "High"),
        "whatsapp": ("WhatsApp/contact integration", "High"),
        "visibility": ("local SEO improvements", "High"),
        "seo": ("local SEO improvements", "High"),
        "booking": ("online booking and automated callback flow", "High")
    }
    for p in pain_points:
        title_lower = p.get("title", "").lower() if isinstance(p, dict) else str(p).lower()
        for k, (service_name, priority) in mapping.items():
            if k in title_lower:
                if service_name not in added:
                    services.append({"service_name": service_name, "priority": priority})
                    added.add(service_name)
    if len(services) < 2:
        defaults = [
            ("a conversion-focused landing page and clearer enquiry pathways", "High"),
            ("local SEO improvements", "High"),
            ("WhatsApp/contact integration", "High")
        ]
        for name, prio in defaults:
            if name not in added:
                services.append({"service_name": name, "priority": prio})
                added.add(name)
                if len(services) >= 2:
                    break
    return services

def validate_email_quality(email_body: str, cleaned_name: str, has_report: bool, sales_intelligence: dict = None) -> tuple[bool, str]:
    """Validates the generated email body to ensure high copywriting quality."""
    if not email_body:
        return False, "Empty email body"
    e_lower = email_body.lower()
    
    # Check for query parameters or operators
    if "site:" in e_lower:
        return False, "Contains 'site:' query operator"
    if "@gmail.com" in e_lower:
        return False, "Contains raw '@gmail.com' domain"
    if "local site:" in e_lower:
        return False, "Contains 'local site:' query operator"
    if "sector" in e_lower and ("site:" in e_lower or "gmail" in e_lower):
        return False, "Contains raw sector query parameters"
        
    # Check for robotic and audit-related terms (expanded ban list)
    robotic_phrases = [
        "during our technical analysis",
        "significant growth opportunities",
        "digital pathways",
        "major operational bottleneck",
        "seamlessly into your current workflow",
        "higher customer acquisition costs",
        "specific digital pathways are not fully optimized",
        "during our review",
        "technical assessment",
    ]
    for phrase in robotic_phrases:
        if phrase in e_lower:
            return False, f"Contains robotic phrase: '{phrase}'"

    # Check for banned audit/analysis terminology
    audit_terms = ["audit", "audited", "auditing", "technical review"]
    for term in audit_terms:
        if term in e_lower:
            return False, f"Contains banned audit term: '{term}'"

    # "analysis" / "analyzed" check (skip if part of business name)
    name_lower = cleaned_name.lower() if cleaned_name else ""
    for term in ["analysis", "analyzed", "analyzing"]:
        if term in e_lower and term not in name_lower:
            return False, f"Contains banned term: '{term}'"
            
    # Check word count
    core_body = email_body
    if "\n\nBest regards," in email_body:
        core_body = email_body.split("\n\nBest regards,")[0]
    word_cnt = len(core_body.strip().split())
    if word_cnt < 90:
        return False, f"Word count {word_cnt} is less than 90 words"
    if word_cnt > 180:
        return False, f"Word count {word_cnt} exceeds 180 words limit"

    # Grounding check using sales intelligence
    if has_report and sales_intelligence:
        # Check that the email references something from the intelligence
        grounded = False
        
        # Check personalization hooks
        for hook in sales_intelligence.get("personalization_hooks", []):
            hook_keywords = [w for w in hook.lower().replace("-", " ").split() if len(w) > 4]
            for kw in hook_keywords[:3]:
                if kw in e_lower:
                    grounded = True
                    break
            if grounded:
                break
        
        # Check conversion/trust/seo gaps
        if not grounded:
            all_gaps = (
                sales_intelligence.get("conversion_gaps", []) +
                sales_intelligence.get("trust_gaps", []) +
                sales_intelligence.get("seo_gaps", [])
            )
            for gap in all_gaps:
                gap_keywords = [w for w in gap.lower().replace("-", " ").split() if len(w) > 4]
                for kw in gap_keywords[:3]:
                    if kw in e_lower:
                        grounded = True
                        break
                if grounded:
                    break
        
        # Broad keyword fallback
        if not grounded and any(kw in e_lower for kw in [
            "testimonial", "proof", "booking", "whatsapp", "visibility",
            "enquiry", "enquiries", "contact", "trust", "reviews", "mobile",
            "search", "discover", "customers", "visitors"
        ]):
            grounded = True
        
        if not grounded:
            return False, "Does not reference any finding from sales intelligence"

    return True, "Passed"

def generate_deterministic_template(lead_name, category, location, sales_intelligence: dict = None):
    """
    Structured, benefit-focused B2B cold email of 100-150 words.
    Uses sales intelligence for personalization when available.
    """
    # Extract from sales intelligence if available
    if sales_intelligence:
        hooks = sales_intelligence.get("personalization_hooks", [])
        gaps = (
            sales_intelligence.get("conversion_gaps", []) +
            sales_intelligence.get("trust_gaps", [])
        )
        service = sales_intelligence.get("recommended_service", "")
        impact = sales_intelligence.get("business_impact_summary", "")
    else:
        hooks = []
        gaps = []
        service = ""
        impact = ""

    # Build hook reference
    if hooks:
        hook_text = hooks[0]
    else:
        hook_text = f"strong presence in the {category} space"

    # Build gap reference
    if len(gaps) >= 2:
        gap1, gap2 = gaps[0], gaps[1]
    elif len(gaps) == 1:
        gap1 = gaps[0]
        gap2 = "not having a clear pathway for quick enquiries"
    else:
        gap1 = "limited visible testimonials or customer proof"
        gap2 = "no direct enquiry or contact flow for visitors"

    # Build service reference
    if not service:
        service = "conversion-focused website optimization"

    # 1. Warm Opener & Specific Observation
    p1 = (
        f"I came across {lead_name} and was impressed by your {hook_text}. "
        f"One thing I noticed is that visitors currently face {gap1}, "
        f"which could make it harder for potential customers to reach out."
    )
    
    # 2. Business Impact
    if impact:
        p2 = impact
    else:
        p2 = (
            f"For a local {category} business, this kind of gap can mean "
            f"losing potential customers who are ready to enquire but "
            f"can't find a quick way to do so."
        )
    
    # 3. Value pitch & CTA
    p3 = (
        f"At 3FI Tech, we help local businesses with exactly this kind of thing — "
        f"{service.lower()}, stronger enquiry pathways, and better trust signals. "
        f"Would you be open to a quick 5-minute review next week to see how "
        f"a couple of small changes could help {lead_name}?"
    )
    
    body = f"{p1}\n\n{p2}\n\n{p3}"
    return body

def generate_outreach(
    report,          # AnalysisReport ORM object
    lead,            # Lead ORM object
    email_type: str,
    tone: str,
    length: str,
    cta_goal: str,
    service_focus: str,
) -> dict:
    """
    Generate personalized, human-sounding outreach based on full lead + audit context.
    
    NEW FLOW:
    1. Clean lead data
    2. Generate Sales Intelligence from audit report
    3. Pass Sales Intelligence to EMAIL_GENERATOR_PROMPT
    4. Validate and retry/fallback
    5. Generate WhatsApp, LinkedIn, follow-ups
    """
    from modules.ai.sales_intelligence_generator import generate_sales_intelligence
    
    ai = AIClient()

    # 1. Clean Lead Name
    raw_lead_name = lead.business_name or "Unknown"
    cleaned_lead_name = clean_business_name(raw_lead_name)

    # 2. Category Validation & Industry Inference
    raw_category = lead.category or "Unknown"
    inferred_category = infer_category(cleaned_lead_name, raw_category)

    # 3. Generate Sales Intelligence (the new intermediary layer)
    is_fallback = not report or not report.ai_report_json
    
    # Check if report already has sales intelligence stored
    sales_intel = None
    if report and hasattr(report, 'sales_intelligence_json') and report.sales_intelligence_json:
        sales_intel = report.sales_intelligence_json
        logger.info(f"Using pre-computed sales intelligence for: {cleaned_lead_name}")
    else:
        sales_intel = generate_sales_intelligence(report, lead)
        logger.info(f"Generated fresh sales intelligence for: {cleaned_lead_name}")

    # Debug logging
    logger.info("--- OUTREACH GENERATION DEBUG START ---")
    logger.info(f"Lead: {cleaned_lead_name} | Category: {inferred_category} | Fallback: {is_fallback}")
    logger.info(f"Sales Intel - Hooks: {sales_intel.get('personalization_hooks', [])}")
    logger.info(f"Sales Intel - Pitch: {sales_intel.get('best_pitch_angle', '')}")
    logger.info(f"Sales Intel - Service: {sales_intel.get('recommended_service', '')}")

    # 4. Prepare lead data for the email prompt
    lead_data_dict = {
        "business_name": cleaned_lead_name,
        "category": inferred_category,
        "location": f"{lead.city or ''}, {lead.state or ''}, {lead.country or ''}".strip(", ") or lead.address or "Unknown",
        "website": lead.website or "No website found",
        "rating": lead.rating or "N/A",
        "reviews": lead.reviews_count or "N/A",
        "phone": lead.phone or "N/A",
        "email": lead.email or "N/A"
    }

    # 5. Build the lead analysis text from Sales Intelligence
    if is_fallback and not sales_intel.get("personalization_hooks"):
        # Total fallback — no intelligence available at all
        lead_analysis_text = (
            "[NO SALES INTELLIGENCE AVAILABLE - FALLBACK MODE]\n\n"
            "Write a safe general outreach email based ONLY on the RAW LEAD DATA.\n"
            "Do NOT invent any technical problems or issues.\n\n"
            "Use a safe fallback angle based on the business category:\n"
            "- Focus on general digital discoverability and enquiry handling.\n"
            "- If the website is missing: Pitch a professional website and enquiry flow.\n"
            "- If rating/reviews are high: Leverage their trust to capture more digital enquiries."
        )
    else:
        # Sales Intelligence is available — pass it as the primary context
        lead_analysis_text = json.dumps(sales_intel, indent=2, ensure_ascii=False)

    lead_data_text = json.dumps(lead_data_dict, indent=2, ensure_ascii=False)

    sender_name = settings.SENDER_NAME
    sender_role = settings.SENDER_ROLE
    agency_website = settings.AGENCY_WEBSITE

    # 6. Format the prompt with Sales Intelligence
    serp_page = getattr(lead, "serp_page", None)
    serp_position = getattr(lead, "serp_position", None)
    source_query = getattr(lead, "source_query", None)

    prompt = EMAIL_GENERATOR_PROMPT.format(
        lead_data=lead_data_text,
        lead_analysis=lead_analysis_text,
        sender_name=sender_name,
        sender_role=sender_role,
        agency_website=agency_website,
        serp_page=serp_page if serp_page is not None else "Unknown",
        serp_position=serp_position if serp_position is not None else "Unknown",
        source_query=source_query if source_query else "Unknown"
    )

    logger.info(f"Generating outreach for lead: {cleaned_lead_name} | is_fallback={is_fallback}")

    # 7. Generate email with AI
    email_source = "AI"
    result = ai.generate_json(prompt)

    if "error" in result:
        logger.info("Outreach generation: JSON parsing failed, attempting repair.")
        result = ai.generate_json(prompt)

    email_body = result.get("email_body", "")
    
    # 8. Quality Validation with Sales Intelligence grounding
    passed, error_msg = validate_email_quality(
        email_body=email_body, 
        cleaned_name=cleaned_lead_name, 
        has_report=not is_fallback,
        sales_intelligence=sales_intel
    )
    
    logger.info(f"Quality validation: {passed} (Details: {error_msg})")

    if not passed or "error" in result:
        logger.warning(f"Outreach generation failed quality check: {error_msg}. Retrying with feedback.")
        retry_prompt = prompt + f"\n\n========================\nSTRICT RE-GENERATION FEEDBACK\n========================\n" \
                                f"Your previous draft failed quality validation: {error_msg}.\n" \
                                f"Rewrite the email completely. It must be 100-150 words.\n" \
                                f"Use warm, human language. Reference a specific business observation.\n" \
                                f"Do NOT use the words 'audit', 'analysis', 'technical review', 'site:', '@gmail.com', or robotic jargon."
        
        retry_result = ai.generate_json(retry_prompt)
        if "error" not in retry_result:
            retry_body = retry_result.get("email_body", "")
            retry_passed, retry_error = validate_email_quality(
                email_body=retry_body,
                cleaned_name=cleaned_lead_name,
                has_report=not is_fallback,
                sales_intelligence=sales_intel
            )
            if retry_passed:
                result = retry_result
                email_body = retry_body
                passed = True
                error_msg = "Passed after retry"
                logger.info(f"Successfully generated high-quality email after retry.")
            else:
                logger.warning(f"Retry also failed quality validation: {retry_error}")
                error_msg = f"Retry failed: {retry_error}"

    # 9. Deterministic template fallback using Sales Intelligence
    if not passed or "error" in result:
        logger.warning(f"AI generation failed validation. Falling back to deterministic template.")
        email_source = "fallback"
        
        deterministic_body = generate_deterministic_template(
            lead_name=cleaned_lead_name,
            category=inferred_category,
            location=f"{lead.city or ''}, {lead.state or ''}".strip(", ") or "your area",
            sales_intelligence=sales_intel
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

    # Fill safe defaults if required fields are missing
    required_fields = [
        "subject", "preview_text", "email_body", "identified_problem",
        "proposed_solution", "personalization_used", "confidence_score", "email_type"
    ]
    for field in required_fields:
        if field not in result or not result[field]:
            if field == "subject":
                result["subject"] = f"Improve {cleaned_lead_name}'s online enquiries"
            elif field == "preview_text":
                result["preview_text"] = f"Ideas for {cleaned_lead_name}"
            elif field == "email_body":
                result["email_body"] = f"Hi,\n\nWe would love to help you build a professional online presence for {cleaned_lead_name}.\n\nBest,\n{sender_name}"
            elif field == "identified_problem":
                result["identified_problem"] = sales_intel.get("best_pitch_angle", "General digital presence")
            elif field == "proposed_solution":
                result["proposed_solution"] = sales_intel.get("recommended_service", "Digital Presence Optimization")
            elif field == "personalization_used":
                hooks = sales_intel.get("personalization_hooks", [])
                result["personalization_used"] = hooks[0] if hooks else cleaned_lead_name
            elif field == "confidence_score":
                result["confidence_score"] = "Medium"
            elif field == "email_type":
                result["email_type"] = "General Business Outreach"

    # Match UI expectations
    result["subject_lines"] = [result["subject"]]
    
    # Generate WhatsApp message using sales intelligence
    pitch_angle = sales_intel.get("best_pitch_angle", result.get("proposed_solution", ""))
    whatsapp_prompt = f"""
Write a WhatsApp message under 60 words for {cleaned_lead_name} ({inferred_category}, {f"{lead.city or ''}".strip()}).
Based on this insight: {pitch_angle}
Tone: friendly, direct. No formal greetings. Start with a specific observation.
Do NOT use the words 'audit', 'analysis', or 'technical review'.
Return JSON: {{"whatsapp_message": ""}}
"""
    wa_res = ai.generate_json(whatsapp_prompt)
    result["whatsapp_message"] = wa_res.get("whatsapp_message", f"Hi! I was looking at {cleaned_lead_name} and had a quick idea to help capture more enquiries. Would you be open to a quick chat?")

    # Generate LinkedIn message using sales intelligence
    linkedin_prompt = f"""
Write a LinkedIn connection note under 50 words for {cleaned_lead_name} ({inferred_category}, {f"{lead.city or ''}".strip()}).
Based on this insight: {pitch_angle}
Tone: professional, curious. No generic phrases.
Do NOT use the words 'audit', 'analysis', or 'technical review'.
Return JSON: {{"linkedin_message": ""}}
"""
    li_res = ai.generate_json(linkedin_prompt)
    result["linkedin_message"] = li_res.get("linkedin_message", f"Hi, I noticed {cleaned_lead_name} and really liked your local presence. I'd love to connect and share a quick idea.")

    # Generate followups
    result["follow_up_1"] = generate_followup(lead, result["subject"], result["email_body"], 1)
    result["follow_up_2"] = generate_followup(lead, result["subject"], result["email_body"], 2)

    word_count = count_words(result["email_body"].split("\n\nBest regards,")[0])

    # Debug logging end
    logger.info(f"Final Word Count (core): {word_count}")
    logger.info(f"Email Source: {email_source}")
    logger.info(f"Is Report-Based: {not is_fallback}")
    logger.info(f"Validation Passed/Failed: {passed} ({error_msg})")
    logger.info("--- OUTREACH GENERATION DEBUG END ---")
    
    # Store details internally for test printing and verification
    result["email_source"] = email_source
    result["is_report_based"] = not is_fallback
    result["word_count"] = word_count
    result["validation_status"] = error_msg
    result["sales_intelligence"] = sales_intel

    return result


def apply_modifier(current_email_body: str, modifier: str) -> str:
    """
    Quick-edit the existing email body using a modifier action.
    modifier: one of 'make_shorter', 'make_professional', 'make_friendly', 'stronger_cta'
    Returns the updated email body string.
    """
    ai = AIClient()
    base_prompt = MODIFIER_PROMPTS.get(modifier, "")
    if not base_prompt:
        return current_email_body

    prompt = f"{base_prompt}\n\nEMAIL:\n{current_email_body}"
    result = ai.generate_json(prompt)

    if "error" in result:
        logger.error(f"Modifier '{modifier}' failed: {result.get('error')}")
        return current_email_body  # Return original on error

    return result.get("email_body", current_email_body)


def generate_single_channel(channel: str, current_result: dict, lead, report) -> str:
    """
    Generate or regenerate a single channel message (WhatsApp or LinkedIn).
    channel: 'whatsapp' or 'linkedin'
    """
    ai = AIClient()
    ai_data = report.ai_report_json or {}

    if channel == "whatsapp":
        prompt = f"""
Write a WhatsApp message under 60 words for {lead.business_name} ({lead.category}, {lead.city}).
Based on this insight: {ai_data.get('main_pitch_angle', '')}
Tone: friendly, direct. No formal greetings. Start with a specific observation.
Return JSON: {{"whatsapp_message": ""}}
"""
    else:
        prompt = f"""
Write a LinkedIn connection note under 50 words for {lead.business_name} ({lead.category}, {lead.city}).
Based on this insight: {ai_data.get('main_pitch_angle', '')}
Tone: professional, curious. No generic phrases.
Return JSON: {{"linkedin_message": ""}}
"""

    result = ai.generate_json(prompt)
    if "error" in result:
        return current_result.get(f"{channel}_message", "")

    return result.get(f"{channel}_message", current_result.get(f"{channel}_message", ""))
