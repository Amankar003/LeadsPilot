import os
import sys
import logging

# Ensure root directory is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_pipeline")

from modules.database.models import Lead, AnalysisReport
from modules.analysis.outreach_generator import (
    generate_outreach, 
    count_words,
    clean_business_name,
    is_invalid_category,
    infer_category,
    normalize_pain_points
)

def run_tests():
    # ==========================================
    # TEST 0: HELPER UTILITY CHECKS
    # ==========================================
    print("\n==========================================")
    print("TEST 0: HELPER UTILITY CHECKS (CLEANING, INFERENCE)")
    print("==========================================\n")

    # Name cleaning check
    raw_name = "Rachel Hogg Creative Arts - Highams Park Portal"
    cleaned_name = clean_business_name(raw_name)
    print(f"Raw Name: {raw_name}")
    print(f"Cleaned Name: {cleaned_name}")
    assert cleaned_name == "Rachel Hogg Creative Arts", f"Error: Clean name failed! Expected 'Rachel Hogg Creative Arts', got '{cleaned_name}'"

    # Category validation check
    bad_cat = 'site:.london "Hotels""@gmail.com"'
    is_bad = is_invalid_category(bad_cat)
    print(f"Raw Category: {bad_cat}")
    print(f"Is Category Invalid: {is_bad}")
    assert is_bad is True, "Error: is_invalid_category failed on query parameter sector!"

    # Category inference check
    inferred_cat = infer_category(cleaned_name, bad_cat)
    print(f"Inferred Category: {inferred_cat}")
    assert inferred_cat == "creative arts education", f"Error: Category inference failed! Got '{inferred_cat}'"

    # Pain points normalization check
    raw_pts = ["Missing social proof", "Missing WhatsApp integration"]
    norm_pts = normalize_pain_points(raw_pts)
    print(f"Raw Pain Points: {raw_pts}")
    print(f"Normalized Pain Points: {[p['title'] for p in norm_pts]}")
    assert "limited visible testimonials or trust-building proof for new visitors" in [p['title'] for p in norm_pts]

    # ==========================================
    # TEST 1: BAD LEAD PIPELINE OVERHAUL GENERATION
    # ==========================================
    print("\n==========================================")
    print("TEST 1: PIPELINE GENERATION WITH INVALID SECTOR & SUFFIX SUITE")
    print("==========================================\n")

    bad_lead = Lead(
        business_name="Rachel Hogg Creative Arts - Highams Park Portal",
        category='site:.london "Hotels""@gmail.com"',
        city="London",
        state="England",
        country="UK",
        address="London, UK",
        website="https://rachelhogg-creativearts.com",
        phone="+442079460192",
        email="info@rachelhogg.com"
    )

    bad_report = AnalysisReport(
        overall_score=72,
        opportunity_level="High",
        opportunity_score=80,
        pain_points_json=[
            {"title": "Missing social proof", "severity": "high"},
            {"title": "Missing WhatsApp integration", "severity": "medium"}
        ],
        recommended_services_json=[
            {"service_name": "Testimonial and Trust Badge Setup", "priority": "High"},
            {"service_name": "WhatsApp Integration Flow", "priority": "High"}
        ],
        ai_report_json={
            "executive_summary": "Rachel Hogg Creative Arts has a strong local footprint but lacks direct online pathways to capture enquiries instantly.",
            "main_pitch_angle": "Adding testimonial sections and direct WhatsApp booking hooks to double local student capture.",
            "top_pain_points": [
                {"title": "Missing social proof", "severity": "high"}
            ],
            "recommended_services": [
                {"service_name": "Testimonial Setup", "priority": "High"}
            ]
        }
    )

    result = generate_outreach(
        report=bad_report,
        lead=bad_lead,
        email_type="Cold Outreach",
        tone="Professional",
        length="Standard",
        cta_goal="Get Reply",
        service_focus="Auto"
    )

    email_body = result.get("email_body", "")
    core_body = email_body.split("\n\nBest regards,")[0]
    word_cnt = count_words(core_body)

    print("SUBJECT:")
    print(result.get("subject"))
    print("\nEMAIL BODY:")
    print(email_body)
    print("\n--- STATS & VALIDATION ---")
    print(f"Core Word Count: {word_cnt}")
    print(f"Email Source: {result.get('email_source')}")
    print(f"Is Report-Based: {result.get('is_report_based')}")
    print(f"Validation Status: {result.get('validation_status')}")

    # Verify Banned and Cleaned Constraints
    assert "Highams Park Portal" not in email_body, "Error: Found suffix noise in generated email!"
    assert "site:" not in email_body.lower(), "Error: Found raw search operators in generated email!"
    assert "@gmail.com" not in core_body.lower(), "Error: Found raw email scraper artifacts in body!"
    assert "during our technical analysis" not in email_body.lower(), "Error: Found banned robotic jargon!"
    assert "significant growth opportunities" not in email_body.lower(), "Error: Found banned robotic jargon!"
    
    assert word_cnt >= 90, f"Error: Core email word count {word_cnt} is less than 90 words!"
    assert word_cnt <= 165, f"Error: Core email word count {word_cnt} exceeds the word target!"

    print("\n[SUCCESS] All outreach pipeline test assertions passed successfully!")

if __name__ == "__main__":
    run_tests()
