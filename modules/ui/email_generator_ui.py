import streamlit as st
import pandas as pd
from config.database import SessionLocal
from modules.database.repositories import CampaignRepository, LeadRepository, LeadInsightRepository, EmailDraftRepository
from modules.database.models import Lead
from modules.ai.email_generator import EmailGenerator
from modules.ui.theme import page_header, empty_state, workflow_indicator
import time


def render_email_generator():
    page_header("✉️", "Email Generator", "Generate personalized outreach emails using AI insights")

    workflow_indicator(
        ["Scrape", "Clean", "AI Analyze", "Generate Email", "Review", "Send"],
        active_index=3
    )

    db = SessionLocal()
    try:
        campaigns = CampaignRepository(db).get_all()

        if not campaigns:
            empty_state("📋", "No Campaigns", "Create a campaign first.")
            return

        camp_options = {c.id: c.campaign_name for c in campaigns}
        selected_camp_id = st.selectbox(
            "🎯 Select Campaign",
            options=list(camp_options.keys()),
            format_func=lambda x: camp_options[x],
            key="email_gen_campaign"
        )

        insight_repo = LeadInsightRepository(db)
        draft_repo = EmailDraftRepository(db)
        lead_repo = LeadRepository(db)

        all_leads = db.query(Lead).filter(
            Lead.campaign_id == selected_camp_id,
            Lead.status == "AI_ANALYZED"
        ).all()

        if not all_leads:
            empty_state("🧠", "No AI-Analyzed Leads", "Analyze leads first in the AI Lead Analysis page.")
            return

        st.markdown(f"##### Found **{len(all_leads)}** leads ready for email generation")
        
        c_f1, c_f2 = st.columns(2)
        with c_f1:
            has_email_only = st.checkbox("📧 Has Email only", key="gen_has_email")
        with c_f2:
            has_phone_only = st.checkbox("📞 Has Phone only", key="gen_has_phone")

        data = []
        for l in all_leads:
            if has_email_only and not l.email:
                continue
            if has_phone_only and not l.phone:
                continue
            insight = insight_repo.get_by_lead_id(l.id)
            data.append({
                "Select": False,
                "ID": l.id,
                "Business Name": l.business_name,
                "Email": l.email or "—",
                "Score": insight.lead_score if insight else 0,
                "Type": insight.lead_type if insight else "—",
            })

        df = pd.DataFrame(data)
        edited_df = st.data_editor(
            df, hide_index=True, width="stretch",
            column_config={
                "Select": st.column_config.CheckboxColumn("✓", default=False),
                "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
            },
            key="email_gen_editor"
        )

        selected_ids = edited_df[edited_df["Select"] == True]["ID"].tolist()

        if st.button("✉️ Generate Emails", type="primary", use_container_width=True):
            if not selected_ids:
                st.warning("Select leads first.")
            else:
                generator = EmailGenerator()
                campaign = CampaignRepository(db).get_by_id(selected_camp_id)
                progress = st.progress(0, text="Preparing…")

                for i, l_id in enumerate(selected_ids):
                    lead = db.query(Lead).filter_by(id=l_id).first()
                    insight = insight_repo.get_by_lead_id(l_id)
                    progress.progress(
                        (i + 1) / len(selected_ids),
                        text=f"✉️ Generating email {i + 1}/{len(selected_ids)}: {lead.business_name[:25]}…" if lead else "Working…"
                    )

                    if lead and insight:
                        lead_data = {
                            "business_name": lead.business_name,
                            "category": lead.category,
                            "phone": lead.phone,
                            "email": lead.email,
                            "website": lead.website,
                            "address": lead.address,
                        }
                        insight_data = {
                            "recommended_service": insight.recommended_service,
                            "reason": insight.reason,
                            "pain_points": insight.pain_points,
                        }
                        draft_data = generator.generate_draft(lead_data, insight_data, campaign.category if campaign else "")

                        draft_repo.create(
                            lead_id=l_id,
                            campaign_id=selected_camp_id,
                            subject=draft_data.get("subject", "Opportunity"),
                            body=draft_data.get("body", "Hello,"),
                            preview_text=draft_data.get("preview_text", ""),
                            identified_problem=draft_data.get("identified_problem", ""),
                            proposed_solution=draft_data.get("proposed_solution", ""),
                            personalization_used=draft_data.get("personalization_used", ""),
                            confidence_score=draft_data.get("confidence_score", ""),
                            email_type=draft_data.get("email_type", ""),
                            generated_by_model="groq",
                        )
                        lead_repo.update_status(l_id, "EMAIL_GENERATED")

                    time.sleep(1)

                progress.progress(1.0, text="✅ Email generation complete!")
                st.balloons()
                st.rerun()
    finally:
        db.close()
