"""
pain_point_engine.py - Converts raw audit facts into structured business pain points.
"""

def generate_pain_points(audit_data: dict) -> list:
    """
    Generate a list of structured pain points from audit data.
    """
    pain_points = []
    
    if not audit_data.get("has_website"):
        pain_points.append({
            "type": "presence",
            "severity": "Critical",
            "title": "No professional website found",
            "description": "The business does not have a reachable website.",
            "evidence": "URL is missing or unreachable.",
            "business_impact": "Customers may not find reliable business information online, reducing trust and inquiries.",
            "recommended_service": "Website Development"
        })
        return pain_points

    # SEO Pain Points
    seo = audit_data.get("seo", {})
    if not seo.get("title_present") or not seo.get("meta_description_present"):
        pain_points.append({
            "type": "seo",
            "severity": "High",
            "title": "Missing essential SEO tags",
            "description": "Crucial meta tags (title or description) are missing.",
            "evidence": "Homepage lacks <title> or <meta name='description'>.",
            "business_impact": "Search engine visibility will be significantly lower, resulting in fewer organic customers.",
            "recommended_service": "Technical SEO"
        })
        
    # CTA / Conversion Pain Points
    cta = audit_data.get("cta", {})
    if cta.get("total_cta_count", 0) == 0 and not cta.get("has_contact_form"):
        pain_points.append({
            "type": "conversion",
            "severity": "Critical",
            "title": "Weak conversion path",
            "description": "No clear call-to-action or contact forms found.",
            "evidence": "No recognizable CTA buttons or forms on homepage.",
            "business_impact": "Website visitors will leave without taking action, wasting traffic.",
            "recommended_service": "CTA & Conversion Optimization"
        })
    elif not cta.get("has_whatsapp_link"):
        pain_points.append({
            "type": "conversion",
            "severity": "Medium",
            "title": "No WhatsApp integration",
            "description": "Missing modern instant messaging CTA.",
            "evidence": "No 'wa.me' or WhatsApp buttons found.",
            "business_impact": "Missed opportunities from mobile users who prefer quick chats over calls.",
            "recommended_service": "WhatsApp Integration"
        })
        
    # Speed Pain Points
    speed = audit_data.get("speed", {})
    if speed.get("speed_rating") == "slow":
        pain_points.append({
            "type": "performance",
            "severity": "High",
            "title": "Slow website loading",
            "description": f"Page load time is excessive ({speed.get('load_time_ms', 0)/1000}s).",
            "evidence": "HTTP request took too long to complete.",
            "business_impact": "High bounce rates as impatient users abandon the site before it loads.",
            "recommended_service": "Speed Optimization"
        })
        
    # Responsive
    responsive = audit_data.get("responsive", {})
    if responsive.get("mobile_friendly_score", 100) < 50:
        pain_points.append({
            "type": "ux",
            "severity": "Critical",
            "title": "Poor mobile readiness",
            "description": "Site lacks responsive design elements.",
            "evidence": "Missing viewport tag or media queries.",
            "business_impact": "Mobile users (often 60%+ of traffic) will have a broken experience.",
            "recommended_service": "Website Redesign"
        })
        
    # Security
    security = audit_data.get("security", {})
    if not security.get("https_enabled"):
        pain_points.append({
            "type": "security",
            "severity": "Critical",
            "title": "Insecure connection (No HTTPS)",
            "description": "The site is running on plain HTTP.",
            "evidence": "URL uses http:// instead of https://.",
            "business_impact": "Browsers will warn users the site is 'Not Secure', killing trust instantly.",
            "recommended_service": "Security Hardening"
        })
        
    # Trust
    trust = audit_data.get("trust", {})
    if not trust.get("has_testimonials") and not trust.get("has_reviews"):
        pain_points.append({
            "type": "trust",
            "severity": "Medium",
            "title": "Missing social proof",
            "description": "No testimonials or reviews found on the homepage.",
            "evidence": "No review keywords or testimonial blocks detected.",
            "business_impact": "Lower conversion rates as new visitors have no proof of past success.",
            "recommended_service": "Landing Page Development"
        })

    # App requirement
    app_req = audit_data.get("app_requirement", {})
    if app_req.get("app_potential") == "High":
        pain_points.append({
            "type": "growth",
            "severity": "Medium",
            "title": "Missing dedicated digital platform",
            "description": "Business relies on basic web presence instead of a dedicated portal/app.",
            "evidence": f"Category is high-potential for apps. {app_req.get('primary_reason')}",
            "business_impact": "Missing out on customer retention, loyalty, and streamlined operations.",
            "recommended_service": app_req.get("recommended_feature", "Mobile App Development")
        })
        
    return pain_points
