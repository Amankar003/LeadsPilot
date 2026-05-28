"""
scoring_engine.py - Calculates Digital Health and Opportunity Scores
"""

def calculate_scores(audit_data: dict) -> dict:
    """
    Calculates digital health and opportunity scores based on audit metrics.
    """
    health = 0
    max_health = 100
    
    if audit_data.get("has_website"):
        # 1. Website Presence & Accessibility (15)
        health += 15
        
        # 2. SEO Basics (20)
        seo = audit_data.get("seo", {})
        if seo.get("title_present"): health += 4
        if seo.get("meta_description_present"): health += 4
        if seo.get("h1_count", 0) > 0: health += 3
        if seo.get("og_present"): health += 3
        if seo.get("schema_markup_present"): health += 3
        if seo.get("robots_txt_accessible"): health += 1
        if seo.get("sitemap_accessible"): health += 2
        
        # 3. Mobile/UX (15)
        responsive = audit_data.get("responsive", {})
        health += (responsive.get("mobile_friendly_score", 0) / 100) * 15
        
        # 4. CTA & Conversion (20)
        cta = audit_data.get("cta", {})
        if cta.get("total_cta_count", 0) > 0: health += 5
        if cta.get("has_contact_form"): health += 5
        if cta.get("has_visible_phone") or cta.get("has_visible_email"): health += 5
        if cta.get("has_whatsapp_link"): health += 5
        
        # 5. Speed (10)
        speed = audit_data.get("speed", {})
        rating = speed.get("speed_rating", "average")
        if rating == "fast": health += 10
        elif rating == "average": health += 5
        else: health += 2
        
        # 6. Security (10)
        security = audit_data.get("security", {})
        if security.get("https_enabled"): health += 4
        if security.get("csp_enabled"): health += 2
        if security.get("hsts_enabled"): health += 2
        if not security.get("server_exposed"): health += 2
        
        # 7. Trust Signals (10)
        trust = audit_data.get("trust", {})
        if trust.get("has_testimonials") or trust.get("has_reviews"): health += 4
        if trust.get("has_about_page"): health += 3
        if trust.get("has_privacy_policy"): health += 3
        
    else:
        # No website
        health = 0
        
    # --- Opportunity Score ---
    # High opportunity = high weakness + high reachability
    opportunity = 100 - health
    
    # Boost if reachable
    if audit_data.get("has_phone") or audit_data.get("has_email"):
        opportunity = min(100, opportunity + 15)
        
    # Categorize
    level = "Low"
    if opportunity >= 80:
        level = "Very High"
    elif opportunity >= 60:
        level = "High"
    elif opportunity >= 40:
        level = "Medium"
        
    return {
        "overall_score": int(health),
        "opportunity_score": int(opportunity),
        "opportunity_level": level
    }
