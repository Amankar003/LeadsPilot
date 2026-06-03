"""
sales_intelligence_generator.py
Generates a structured Sales Intelligence object from raw audit data.
This layer sits between the audit engine and the email generator,
translating technical findings into sales-ready, human-sounding insights.
"""
import json
from modules.ai.ai_client import AIClient
from modules.ai.prompts import SALES_INTELLIGENCE_PROMPT
from utils.logging_utils import get_logger

logger = get_logger(__name__)


def generate_sales_intelligence(report, lead) -> dict:
    """
    Generate a structured Sales Intelligence object from an AnalysisReport + Lead.

    Args:
        report: AnalysisReport ORM object (may be None for fallback)
        lead: Lead ORM object

    Returns:
        dict with keys: business_summary, strong_points, personalization_hooks,
        top_observations, conversion_gaps, trust_gaps, seo_gaps,
        business_impact_summary, best_pitch_angle, recommended_service, recommended_cta
    """
    if not report or not report.ai_report_json:
        logger.info(f"No report available for {lead.business_name}, using fallback intelligence builder.")
        return _build_fallback_intelligence(lead, report)

    ai = AIClient()

    # Assemble audit context for the prompt
    raw_audit = report.raw_audit_json or {}
    ai_report = report.ai_report_json or {}
    pain_points = report.pain_points_json or []
    recommendations = report.recommended_services_json or []

    audit_context = {
        "business_name": lead.business_name or "Unknown",
        "category": lead.category or "Unknown",
        "location": _build_location(lead),
        "website": lead.website or "No website",
        "rating": lead.rating,
        "reviews_count": lead.reviews_count,
        "has_website": report.has_website,
        "overall_score": report.overall_score,
        "opportunity_level": report.opportunity_level,
        "seo": raw_audit.get("seo", {}),
        "cta": raw_audit.get("cta", {}),
        "trust": raw_audit.get("trust", {}),
        "speed": raw_audit.get("speed", {}),
        "security": raw_audit.get("security", {}),
        "responsive": raw_audit.get("responsive", {}),
        "site_info": raw_audit.get("site_info", {}),
        "serp_page": getattr(lead, "serp_page", None),
        "serp_position": getattr(lead, "serp_position", None),
        "source_query": getattr(lead, "source_query", None),
        "pain_points": pain_points,
        "recommended_services": recommendations,
        "ai_executive_summary": ai_report.get("executive_summary", ""),
        "ai_main_pitch_angle": ai_report.get("main_pitch_angle", ""),
        "ai_business_impact_summary": ai_report.get("business_impact_summary", ""),
    }

    # Add SERP context explicitly to the prompt format
    serp_page = getattr(lead, "serp_page", None)
    serp_position = getattr(lead, "serp_position", None)
    source_query = getattr(lead, "source_query", None)

    prompt = SALES_INTELLIGENCE_PROMPT.format(
        audit_context=json.dumps(audit_context, indent=2, ensure_ascii=False),
        serp_page=serp_page if serp_page is not None else "Unknown",
        serp_position=serp_position if serp_position is not None else "Unknown",
        source_query=source_query if source_query else "Unknown"
    )

    logger.info(f"Generating sales intelligence for: {lead.business_name}")
    result = ai.generate_json(prompt, max_tokens=2000)

    # Validate the result has the required structure
    required_keys = [
        "business_summary", "strong_points", "personalization_hooks",
        "top_observations", "conversion_gaps", "trust_gaps", "seo_gaps",
        "business_impact_summary", "best_pitch_angle",
        "recommended_service", "recommended_cta"
    ]

    if "error" in result or not all(k in result for k in required_keys):
        logger.warning(f"Sales intelligence LLM generation failed or incomplete for {lead.business_name}. Using fallback builder.")
        return _build_fallback_intelligence(lead, report)

    # Ensure list fields are actually lists
    for list_key in ["strong_points", "personalization_hooks", "top_observations",
                     "conversion_gaps", "trust_gaps", "seo_gaps"]:
        if not isinstance(result.get(list_key), list):
            result[list_key] = []

    # Ensure string fields are strings
    for str_key in ["business_summary", "business_impact_summary", "best_pitch_angle",
                    "recommended_service", "recommended_cta"]:
        if not isinstance(result.get(str_key), str):
            result[str_key] = ""

    logger.info(f"Sales intelligence generated successfully for: {lead.business_name}")
    return result


def _build_location(lead) -> str:
    """Build a clean location string from lead fields."""
    parts = [lead.city or "", lead.state or "", lead.country or ""]
    location = ", ".join(p for p in parts if p.strip())
    return location or lead.address or "Unknown"


def _build_fallback_intelligence(lead, report=None) -> dict:
    """
    Deterministic fallback: build a sales intelligence object
    from raw lead data and report without an LLM call.
    """
    business_name = lead.business_name or "the business"
    category = lead.category or "local service business"
    location = _build_location(lead)
    has_website = bool(lead.website)

    # --- Strong Points ---
    strong_points = []
    if lead.rating and float(lead.rating) >= 4.0:
        strong_points.append(f"strong customer rating ({lead.rating} stars)")
    if lead.reviews_count and int(lead.reviews_count) > 10:
        strong_points.append(f"established review presence ({lead.reviews_count} reviews)")
    if has_website:
        strong_points.append("has an existing website")

    if report and report.raw_audit_json:
        raw = report.raw_audit_json
        trust = raw.get("trust", {})
        speed = raw.get("speed", {})
        responsive = raw.get("responsive", {})

        if trust.get("has_testimonials"):
            strong_points.append("testimonials present on website")
        if trust.get("has_portfolio") or trust.get("has_gallery"):
            strong_points.append("portfolio or gallery showcase present")
        if speed.get("is_fast", False):
            strong_points.append("fast-loading website")
        if responsive.get("is_mobile_friendly", False):
            strong_points.append("mobile-friendly design")

    if not strong_points:
        strong_points.append("established local presence")

    # --- Personalization Hooks ---
    hooks = []
    if report and report.ai_report_json:
        ai_r = report.ai_report_json
        summary = ai_r.get("executive_summary", "")
        if summary:
            hooks.append(f"known for {category} services in {location}")
    if lead.rating and float(lead.rating) >= 4.0:
        hooks.append(f"strong local reputation with {lead.rating}-star rating")
    if has_website:
        hooks.append("invests in online presence")
    if not hooks:
        hooks.append(f"operates in the {category} space")

    # --- Gaps ---
    conversion_gaps = []
    trust_gaps = []
    seo_gaps = []
    top_observations = []

    if report and report.raw_audit_json:
        raw = report.raw_audit_json
        cta = raw.get("cta", {})
        trust_data = raw.get("trust", {})
        seo = raw.get("seo", {})
        site_info = raw.get("site_info", {})

        # Conversion gaps
        missing_features = cta.get("missing_features", []) or site_info.get("missing_features", [])
        for feat in missing_features:
            feat_lower = str(feat).lower()
            if "form" in feat_lower or "enquiry" in feat_lower or "contact" in feat_lower:
                conversion_gaps.append("no enquiry form or contact pathway")
            elif "whatsapp" in feat_lower:
                conversion_gaps.append("no WhatsApp button for quick mobile contact")
            elif "booking" in feat_lower or "appointment" in feat_lower:
                conversion_gaps.append("no online booking or appointment system")
            elif "cta" in feat_lower or "call to action" in feat_lower:
                conversion_gaps.append("no clear call-to-action for visitors")

        if not cta.get("has_primary_cta", True):
            conversion_gaps.append("no prominent call-to-action on homepage")

        # Trust gaps
        if not trust_data.get("has_testimonials", True):
            trust_gaps.append("no visible testimonials or reviews")
        if not trust_data.get("has_privacy_policy", True):
            trust_gaps.append("no privacy policy page")
        if not trust_data.get("has_certifications", True):
            trust_gaps.append("no certifications or trust badges displayed")

        # SEO gaps
        if not seo.get("has_meta_description", True):
            seo_gaps.append("missing meta description, reducing search visibility")
        if not seo.get("has_title_tag", True):
            seo_gaps.append("missing or generic page title")
        if seo.get("missing_alt_tags", 0) > 3:
            seo_gaps.append("multiple images missing alt text")

        # Top observations from pain points
        if report.pain_points_json:
            for pp in report.pain_points_json[:3]:
                title = pp.get("title", "") if isinstance(pp, dict) else str(pp)
                if title:
                    top_observations.append(title)

    elif not has_website:
        conversion_gaps.append("no website to capture online enquiries")
        trust_gaps.append("no online presence for visitors to verify credibility")
        seo_gaps.append("invisible in local search results")
        top_observations.append("business has no website")

    # Deduplicate
    conversion_gaps = list(dict.fromkeys(conversion_gaps))[:4]
    trust_gaps = list(dict.fromkeys(trust_gaps))[:4]
    seo_gaps = list(dict.fromkeys(seo_gaps))[:3]

    if not top_observations:
        if conversion_gaps:
            top_observations.append(conversion_gaps[0])
        if trust_gaps:
            top_observations.append(trust_gaps[0])

    # --- Business Impact Summary ---
    if conversion_gaps:
        impact = f"Visitors to {business_name} may find it difficult to enquire or book quickly, which means potential customers could be choosing competitors instead."
    elif not has_website:
        impact = f"Without a website, {business_name} is missing out on customers who search online for {category} services in {location}."
    else:
        impact = f"Small improvements to the online presence of {business_name} could help capture more enquiries from local customers."

    # --- Best Pitch Angle ---
    if not has_website:
        pitch = "Help the business establish a professional online presence to capture local search traffic"
    elif conversion_gaps:
        pitch = "Improve the enquiry and conversion flow so visitors can contact or book easily"
    elif trust_gaps:
        pitch = "Strengthen trust signals so first-time visitors feel confident reaching out"
    elif seo_gaps:
        pitch = "Improve search visibility so more local customers can discover the business"
    else:
        pitch = "Optimize the digital presence to capture more local enquiries"

    # --- Recommended Service ---
    if not has_website:
        service = "Website Development & Local SEO"
    elif conversion_gaps:
        service = "Conversion-Focused Website Optimization"
    elif seo_gaps:
        service = "Local SEO & Content Optimization"
    else:
        service = "Digital Presence Optimization"

    # --- CTA ---
    cta = "Would you be open to a quick 5-minute review to see how a few small changes could help?"

    return {
        "business_summary": f"{business_name} is a {category} business based in {location}.",
        "strong_points": strong_points,
        "personalization_hooks": hooks,
        "top_observations": top_observations,
        "conversion_gaps": conversion_gaps,
        "trust_gaps": trust_gaps,
        "seo_gaps": seo_gaps,
        "business_impact_summary": impact,
        "best_pitch_angle": pitch,
        "recommended_service": service,
        "recommended_cta": cta,
    }
