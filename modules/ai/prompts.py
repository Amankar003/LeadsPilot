LEAD_ANALYSIS_PROMPT = """
You are an expert sales strategist. Analyze the following lead details and provide structured insights.
Lead Details:
{lead_details}

Campaign Service Focus: {service_focus}

Respond ONLY with valid JSON in this exact format:
{{
  "recommended_service": "Short string of recommended service to pitch",
  "reason": "1-2 sentence reason why this service fits them based on their data",
  "pain_points": ["point 1", "point 2"],
  "lead_score_adjustment": 0,
  "lead_type_recommendation": "HOT/WARM/COLD"
}}
"""

EMAIL_GENERATOR_PROMPT = """
You are an expert copywriter. Write a highly personalized, short, and natural cold outreach email.
Do NOT use placeholders like [Name]. If a field is missing, adapt.
Keep it under 120 words. No overpromising. Soft CTA.

Lead details:
{lead_details}

Insights:
{insights}

Campaign Service Focus: {service_focus}

Respond ONLY with valid JSON in this exact format:
{{
  "subject": "Email Subject",
  "body": "Email body content.\\n\\nIf this is not relevant, you can reply 'unsubscribe' and I won't follow up."
}}
"""

FOLLOWUP_GENERATOR_PROMPT = """
You are an expert copywriter. Write a polite, short follow-up to the previous email.
Keep it natural, under 80 words, not pushy. Mention the previous email briefly.

Lead details:
{lead_details}

Original Email Subject: {original_subject}
Original Email Body: {original_body}

Follow-up Number: {followup_number}

Respond ONLY with valid JSON in this exact format:
{{
  "subject": "Re: Email Subject",
  "body": "Follow-up body content.\\n\\nIf this is not relevant, you can reply 'unsubscribe' and I won't follow up."
}}
"""
