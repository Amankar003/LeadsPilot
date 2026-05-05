import streamlit as st
import pandas as pd
from config.database import SessionLocal
from modules.database.repositories import CampaignRepository, LeadRepository, LeadInsightRepository
from modules.database.models import Lead, LeadInsight
from modules.ai.lead_analyzer import LeadAnalyzer
from modules.ui.theme import page_header, empty_state, status_badge, workflow_indicator
import time


def render_ai_lead_analysis():
    page_header("🧠", "AI Lead Analysis", "Use Groq AI (Llama 3.3) to score leads, identify pain points, and recommend services")

    workflow_indicator(
        ["Scrape", "Clean", "AI Analyze", "Generate Email", "Review Draft", "Send"],
        active_index=2
    )

    db = SessionLocal()
    try:
        campaigns = CampaignRepository(db).get_all()

        if not campaigns:
            empty_state("📋", "No Campaigns", "Create a campaign and scrape some leads first.")
            return

        camp_options = {c.id: c.campaign_name for c in campaigns}
        selected_camp_id = st.selectbox(
            "🎯 Select Campaign",
            options=list(camp_options.keys()),
            format_func=lambda x: camp_options[x],
            key="ai_analysis_campaign"
        )

        insight_repo = LeadInsightRepository(db)
        campaign_leads = db.query(Lead).filter(Lead.campaign_id == selected_camp_id).all()

        if not campaign_leads:
            empty_state("👥", "No Leads", "No leads found for this campaign. Run the scraping job first.")
            return

        # Filters
        c_f1, c_f2 = st.columns(2)
        with c_f1:
            has_email_only = st.checkbox("📧 Has Email only", key="ai_has_email")
        with c_f2:
            has_phone_only = st.checkbox("📞 Has Phone only", key="ai_has_phone")

        analyzed_lead_ids = set(
            row.lead_id for row in db.query(LeadInsight.lead_id).all()
        )
        
        # Apply filters to leads
        filtered_leads = []
        for l in campaign_leads:
            if has_email_only and not l.email:
                continue
            if has_phone_only and not l.phone:
                continue
            filtered_leads.append(l)
        
        campaign_leads = filtered_leads
        unanalyzed_leads = [l for l in campaign_leads if l.id not in analyzed_lead_ids]
        analyzed_leads = [l for l in campaign_leads if l.id in analyzed_lead_ids]

        # Metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📊 Total Leads", len(campaign_leads))
        c2.metric("⏳ Pending", len(unanalyzed_leads))
        c3.metric("✅ Analyzed", len(analyzed_leads))
        hot = sum(1 for l in analyzed_leads if insight_repo.get_by_lead_id(l.id) and insight_repo.get_by_lead_id(l.id).lead_type == "HOT")
        c4.metric("🔥 Hot", hot)

        # ── Unanalyzed leads ──
        if unanalyzed_leads:
            st.divider()
            st.markdown("##### ⏳ Leads Pending Analysis")
            data = []
            for l in unanalyzed_leads:
                data.append({
                    "Select": False,
                    "ID": l.id,
                    "Business Name": l.business_name,
                    "Category": l.category or "",
                    "Website": l.website or "",
                    "Phone": l.phone or "",
                })

            df = pd.DataFrame(data)
            edited_df = st.data_editor(
                df, hide_index=True, width="stretch",
                column_config={"Select": st.column_config.CheckboxColumn("✓", default=False)},
                key="ai_analysis_editor"
            )

            selected_ids = edited_df[edited_df["Select"] == True]["ID"].tolist()

            col_a, col_b, _ = st.columns([1, 1, 2])
            with col_a:
                if st.button("🧠 Analyze Selected", type="primary", use_container_width=True):
                    if not selected_ids:
                        st.warning("Select leads first.")
                    else:
                        _analyze_leads(db, selected_ids, selected_camp_id)
                        st.rerun()
            with col_b:
                if st.button("⚡ Quick Analyze (Top 20)", use_container_width=True):
                    top_ids = [l.id for l in unanalyzed_leads[:20]]
                    if top_ids:
                        _analyze_leads(db, top_ids, selected_camp_id)
                        st.rerun()

        # ── Analyzed leads ──
        st.divider()
        st.markdown("##### ✅ Analyzed Leads")
        if analyzed_leads:
            a_data = []
            for l in analyzed_leads:
                insight = insight_repo.get_by_lead_id(l.id)
                if insight:
                    a_data.append({
                        "Business Name": l.business_name,
                        "Service": insight.recommended_service or "",
                        "Score": insight.lead_score,
                        "Type": insight.lead_type or "",
                        "Pain Points": ", ".join(insight.pain_points) if isinstance(insight.pain_points, list) else str(insight.pain_points or ""),
                        "Reason": insight.reason or "",
                    })
            if a_data:
                adf = pd.DataFrame(a_data)
                st.dataframe(
                    adf,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
                        "Type": st.column_config.TextColumn("Type", width="small"),
                    }
                )
            else:
                empty_state("📊", "No Insights Yet", "Analyze leads to see results here.")
        else:
            empty_state("📊", "No Analyzed Leads", "Select leads above and click Analyze to get started.")
    finally:
        db.close()


def _analyze_leads(db, lead_ids, campaign_id):
    lead_repo = LeadRepository(db)
    insight_repo = LeadInsightRepository(db)
    campaign = CampaignRepository(db).get_by_id(campaign_id)
    analyzer = LeadAnalyzer()

    progress_bar = st.progress(0, text="Preparing analysis…")

    for i, l_id in enumerate(lead_ids):
        lead = db.query(Lead).filter(Lead.id == l_id).first()
        if not lead:
            continue

        progress_bar.progress(
            (i + 1) / len(lead_ids),
            text=f"🧠 Analyzing {i + 1}/{len(lead_ids)}: {lead.business_name[:30]}…"
        )

        lead_data = {
            "business_name": lead.business_name,
            "category": lead.category,
            "phone": lead.phone,
            "email": lead.email,
            "website": lead.website,
            "address": lead.address,
            "rating": lead.rating,
            "reviews_count": lead.reviews_count,
            "source": lead.source,
            "raw_data": lead.raw_data,
            "has_email": lead.has_email,
            "has_phone": lead.has_phone,
            "has_website": lead.has_website,
        }
        insight_data = analyzer.analyze_lead(lead_data, campaign.category if campaign else "")

        insight_repo.create(
            lead_id=l_id,
            recommended_service=insight_data.get("recommended_service"),
            reason=insight_data.get("reason"),
            pain_points=insight_data.get("pain_points"),
            lead_score=insight_data.get("lead_score"),
            lead_type=insight_data.get("lead_type"),
            ai_model="groq",
            ai_response=insight_data.get("ai_response"),
        )
        lead_repo.update_status(l_id, "AI_ANALYZED")
        time.sleep(1)

    progress_bar.progress(1.0, text="✅ Analysis complete!")
