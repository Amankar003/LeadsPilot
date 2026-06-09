import streamlit as st
import pandas as pd
from config.database import SessionLocal
from modules.database.repositories import CampaignRepository, JobRepository
from modules.ai_pipeline.service import AIPipelineService
from modules.ui.theme import make_dataframe_arrow_compatible
import json

def _render_results(results, campaigns, job_repo, db, key_prefix):
    if not results:
        return
    st.markdown("---")
    st.markdown("### 🎯 Generated Results")
    
    for idx, res in enumerate(results):
        # Safe parsing incase LLM returns flat or nested structure
        dork_payload = res.get("dork_payload", res)
        dorks_list = dork_payload.get("dorks", [])
        
        # Card Aesthetic
        potential = dork_payload.get('lead_potential_range', 'Unknown')
        conf = dork_payload.get('confidence_score', 0)
        conf_color = "green" if conf >= 80 else ("orange" if conf >= 60 else "red")
        
        st.markdown(f"""
        <div style="border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin-bottom: 20px; background-color: #f8fafc;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h4 style="margin: 0; color: #0f172a;">📊 Opportunity {idx+1}</h4>
                <span style="background-color: {conf_color}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 12px; font-weight: bold;">
                    Confidence: {conf}/100
                </span>
            </div>
            <p style="margin-top: 10px; font-size: 14px;"><strong>Target Persona:</strong> {dork_payload.get('target_persona', 'N/A')}</p>
            <p style="font-size: 14px; color: #475569;"><strong>Service Fit:</strong> {dork_payload.get('service_fit', 'N/A')}</p>
            <p style="font-size: 14px; color: #475569;"><strong>Recommended Keywords:</strong> {', '.join(dork_payload.get('keywords', []))}</p>
            <p style="font-size: 16px; font-weight: 500; color: #2563eb;"><strong>Estimated Lead Potential:</strong> {potential}</p>
        </div>
        """, unsafe_allow_html=True)
        
        if dorks_list:
            df_dorks = pd.DataFrame([{"Select": True, "Dork": d.get("dork",""), "Reason": d.get("reason","")} for d in dorks_list])
            df_dorks["Select"] = df_dorks["Select"].astype(bool)
            df_dorks = make_dataframe_arrow_compatible(df_dorks)
            
            edited_df = st.data_editor(
                df_dorks,
                hide_index=True,
                key=f"{key_prefix}_ai_dork_editor_{idx}",
                column_config={
                    "Select": st.column_config.CheckboxColumn("Select", default=True),
                    "Dork": st.column_config.TextColumn("Dork", disabled=True),
                    "Reason": st.column_config.TextColumn("Why this dork?", disabled=True),
                }
            )
            
            selected_dorks = edited_df[edited_df["Select"] == True]["Dork"].tolist()
            
            # Campaign Dispatcher
            st.markdown("##### ⚙️ Target Campaign Selection")
            sc1, sc2 = st.columns([2, 1])
            with sc1:
                if campaigns:
                    camp_options = {c.id: f"{c.campaign_name} ({c.status})" for c in campaigns}
                    selected_camp_id = st.selectbox(
                        "Select Campaign to receive leads",
                        options=list(camp_options.keys()),
                        format_func=lambda x: camp_options[x],
                        key=f"{key_prefix}_ai_camp_select_{idx}"
                    )
                else:
                    st.warning("No campaigns available. Create one first.")
                    selected_camp_id = None
            
            with sc2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button(f"Send {len(selected_dorks)} Dorks to Scraper", key=f"{key_prefix}_ai_send_scraper_{idx}", type="primary", disabled=not selected_camp_id or not selected_dorks):
                    from modules.database.models import get_or_create_default_user
                    user = get_or_create_default_user(db)
                    created_jobs = 0
                    for dork_query in selected_dorks:
                        job = job_repo.create_job(
                            user_id=user.id,
                            campaign_id=selected_camp_id,
                            platform="serper_bulk",
                            keyword=dork_query,
                            location="Global",
                            num_results=30
                        )
                        if job:
                            created_jobs += 1
                    st.success(f"Dispatched {created_jobs} jobs to the Bulk Scraper queue!")


def render_free_prompt_tab():
    st.markdown("### 💡 Free Prompts")
    st.markdown("Use natural language to discover advanced opportunities and generate highly-targeted search dorks.")
    
    db = SessionLocal()
    campaign_repo = CampaignRepository(db)
    job_repo = JobRepository(db)
    campaigns = campaign_repo.get_all() or []
    
    transfer_intent = st.session_state.get("ai_transfer_intent", "")
    service = AIPipelineService()
    
    with st.form("ai_prompt_form"):
        prompt = st.text_area("Describe your ideal B2B lead (Intent)", value=transfer_intent, placeholder="e.g. Find dental clinics in London struggling with lead generation")
        location = st.text_input("Target Location", value=st.session_state.get("ai_transfer_location", "Global"))
        submitted = st.form_submit_button("Generate Opportunities & Dorks", type="primary")
        
        if submitted and prompt:
            with st.spinner("🧠 Analyzing intent and generating high-potential dorks..."):
                result = service.run_mode_2_free_prompt(prompt, location)
                st.session_state["free_prompt_result"] = [result]
                
    if transfer_intent:
        if st.button("Clear Transferred Data"):
            st.session_state.pop("ai_transfer_intent", None)
            st.session_state.pop("ai_transfer_location", None)
            st.rerun()

    _render_results(st.session_state.get("free_prompt_result", []), campaigns, job_repo, db, "free_prompt")


def render_ai_pipeline_tab():
    st.markdown("### 🤖 Advanced AI Dork Pipeline")
    st.markdown("Automatically fetch the latest news and GDELT trends, then generate advanced dorks for them.")
    
    db = SessionLocal()
    campaign_repo = CampaignRepository(db)
    job_repo = JobRepository(db)
    campaigns = campaign_repo.get_all() or []
    service = AIPipelineService()
    
    force_refresh = st.checkbox("Force refresh live trends (bypass cache)", value=False)
    if st.button("Run AI Trend Analysis", type="primary"):
        with st.spinner("🤖 Fetching Shared Trends and building AI Dorks..."):
            results = service.run_mode_1_trend_based(force_refresh=force_refresh)
            st.session_state["ai_generated_trends_results"] = results
            st.session_state["ai_pipeline_completed"] = True
            
            # extract all dorks for optimization
            all_dorks = []
            for res in results:
                dp = res.get("dork_payload", res)
                for d in dp.get("dorks", []):
                    all_dorks.append(d.get("dork", ""))
            st.session_state["ai_generated_dorks"] = all_dorks

    results = st.session_state.get("ai_generated_trends_results", [])
    completed = st.session_state.get("ai_pipeline_completed", False)
    
    if completed:
        st.success("AI trend analysis completed.")
        
        _render_results(results, campaigns, job_repo, db, "ai_pipeline")
        
        st.markdown("---")
        
        dorks = st.session_state.get("ai_generated_dorks", [])
        if dorks:
            st.markdown("### ✨ Optimize Existing Dorks")
            with st.form("ai_optimize_form"):
                intent = st.text_input("What is the goal of these dorks?", value="Extract B2B lead contacts")
                optimize_btn = st.form_submit_button("Optimize Generated Dorks with AI", type="primary")
                if optimize_btn:
                    with st.spinner("✨ Enhancing dorks..."):
                        opt_result = service.run_mode_3_optimize(dorks, intent)
                        st.session_state["optimized_dorks_result"] = [opt_result]
            
            _render_results(st.session_state.get("optimized_dorks_result", []), campaigns, job_repo, db, "optimized")

    # Handle dorks transferred from manual generator
    transfer_dorks = st.session_state.get("ai_transfer_dorks", [])
    if transfer_dorks:
        st.info("Dorks transferred from Manual Generator available for optimization.")
        with st.form("ai_optimize_transfer_form"):
            intent_trans = st.text_input("Goal for transferred dorks?", value="Extract B2B lead contacts")
            optimize_trans_btn = st.form_submit_button("Optimize Transferred Dorks", type="primary")
            if optimize_trans_btn:
                with st.spinner("✨ Enhancing transferred dorks..."):
                    opt_result = service.run_mode_3_optimize(transfer_dorks, intent_trans)
                    st.session_state["optimized_dorks_result_trans"] = [opt_result]
                    
        if st.button("Clear Transferred Dorks"):
            st.session_state.pop("ai_transfer_dorks", None)
            st.rerun()
            
        _render_results(st.session_state.get("optimized_dorks_result_trans", []), campaigns, job_repo, db, "optimized_trans")
