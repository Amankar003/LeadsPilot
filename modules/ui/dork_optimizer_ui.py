import streamlit as st
import pandas as pd
from config.database import SessionLocal
from modules.database.repositories import CampaignRepository
from modules.dork_optimizer.service import DorkOptimizerService
from modules.dork_optimizer.constants import TARGET_SERVICES, DORK_PATTERNS
from modules.ui.theme import page_header, empty_state, make_dataframe_arrow_compatible
import logging

logger = logging.getLogger(__name__)

from modules.ui.components.campaign_creator import create_campaign_modal
from modules.ui.components.opportunity_card import render_opportunity_card
from modules.ui.components.dork_list import render_dork_list
from modules.ui.components.campaign_selector import render_campaign_selector

def render_dork_optimizer():
    page_header("🔍", "Dork Optimizer", "Proactively discover rising B2B trends and compile hyper-targeted search dorks to scrape premium leads.")
    
    db = SessionLocal()
    try:
        service = DorkOptimizerService(db)
        campaign_repo = CampaignRepository(db)
        campaigns = campaign_repo.get_all() or []
        
        # Tabs
        tab1, tab2, tab3 = st.tabs(["🚀 Run Opportunity Pipeline", "🎛️ Manual Dork Generator", "🧠 Dork Intelligence Dashboard"])
        
        # ----------------------------------------------------
        # TAB 1: RUN PIPELINE
        # ----------------------------------------------------
        with tab1:
            st.markdown("#### 1. Configure Discovery Parameters")
            
            c1, c2, c3 = st.columns(3)
            with c1:
                trend_scope = st.selectbox(
                    "Trend Scope",
                    options=["Global", "Specific Country", "Specific Category"],
                    key="do_trend_scope"
                )
                target_service = st.selectbox(
                    "Primary Pitch Service",
                    options=[None] + TARGET_SERVICES,
                    format_func=lambda x: x if x else "All Services (Auto-match)",
                    key="do_target_service"
                )
            with c2:
                country = st.text_input(
                    "Target Country (optional)",
                    placeholder="e.g. US, UK, UAE, India",
                    disabled=(trend_scope == "Specific Category"),
                    key="do_country"
                )
                state = st.text_input(
                    "Target State (optional)",
                    placeholder="e.g. New York, Dubai, London",
                    key="do_state"
                )
            with c3:
                category = st.text_input(
                    "Target Category (optional)",
                    placeholder="e.g. Healthcare, Real Estate, Retail",
                    disabled=(trend_scope == "Specific Country"),
                    key="do_category"
                )
                region = st.text_input(
                    "Target Region/City (optional)",
                    placeholder="e.g. Brooklyn, Manhattan",
                    key="do_region"
                )
                
            with st.expander("⚙️ Advanced Pipeline Settings"):
                ac1, ac2 = st.columns(2)
                with ac1:
                    num_opportunities = st.slider("Max Opportunities", min_value=1, max_value=15, value=5)
                    dorks_per_opportunity = st.slider("Dorks per Opportunity", min_value=1, max_value=10, value=5)
                with ac2:
                    exclude_directories = st.toggle("Exclude directories (Yelp, Justdial, Bayut, etc.)", value=True)
                    exclude_jobs_blogs = st.toggle("Exclude career postings, news, blogs, and PDFs", value=True)

            if st.button("Run Trend Pipeline", type="primary", use_container_width=True):
                with st.spinner("🤖 Fetching live trends and compiling opportunities..."):
                    pipeline_config = {
                        "trend_scope": trend_scope,
                        "country": country,
                        "state": state,
                        "category": category,
                        "region": region,
                        "target_service": target_service,
                        "num_opportunities": num_opportunities,
                        "dorks_per_opportunity": dorks_per_opportunity,
                        "exclude_directories": exclude_directories,
                        "exclude_jobs_blogs_news": exclude_jobs_blogs
                    }
                    
                    try:
                        res = service.run_pipeline(pipeline_config)
                        st.session_state["pipeline_result"] = res
                        st.success(f"Pipeline run completed! Discovered {len(res['opportunities'])} market opportunities and compiled {res['dorks_count']} dorks.")
                    except Exception as e:
                        st.error(f"Failed to run pipeline: {e}")
                        
            # Render results if present
            pipeline_result = st.session_state.get("pipeline_result")
            if pipeline_result:
                st.markdown("---")
                st.markdown("### 🎯 Market Opportunities Found")
                
                opportunities = pipeline_result["opportunities"]
                if not opportunities:
                    st.info("No matching trends discovered. Try broadening your scope filters.")
                else:
                    for opp_idx, opp in enumerate(opportunities):
                        opp_data = {
                            "category": opp.category,
                            "region": opp.region,
                            "country": opp.country,
                            "trend_summary": opp.trend_summary,
                            "opportunity_reason": opp.opportunity_reason,
                            "target_service": getattr(opp, "target_service", "Not specified"),
                            "suggested_offer": opp.suggested_offer,
                            "score": opp.score
                        }
                        render_opportunity_card(opp_data)
                        
                        # Load generated dorks for this opportunity
                        from modules.database.models import GeneratedDork
                        opp_dorks = db.query(GeneratedDork).filter(GeneratedDork.opportunity_id == opp.id).all()
                        
                        selected_dork_ids = render_dork_list(opp_dorks, opp_id=f"opp_{opp_idx}")
                        
                        # Campaign dispatcher
                        render_campaign_selector(db, service, selected_dork_ids, opp_id=f"opp_{opp_idx}")
                        
                        st.markdown("---")
                        
        # ----------------------------------------------------
        # TAB 2: MANUAL GENERATOR
        # ----------------------------------------------------
        with tab2:
            st.markdown("#### 1. Define Search Target Parameters")
            
            mc1, mc2 = st.columns(2)
            with mc1:
                m_country = st.text_input("Target Country", "US", key="m_country")
                m_state = st.text_input("Target State/Province (optional)", "New York", key="m_state")
                m_region = st.text_input("Target Region/City", "Brooklyn", key="m_region")
                m_category = st.text_input("Target Industry Category", "Dental Clinic", key="m_category")
                m_subcategory = st.text_input("Sub-Category / Specialization (optional)", "Cosmetic Dentistry", key="m_subcategory")
            with mc2:
                m_service = st.selectbox("Pitch Target Service", TARGET_SERVICES, index=1, key="m_service")
                m_inc_kw = st.text_input("Must Include Keywords (comma-separated)", "", key="m_inc_kw")
                m_exc_kw = st.text_input("Must Exclude Keywords (comma-separated)", "", key="m_exc_kw")
                m_dork_count = st.slider("Number of Dorks", min_value=1, max_value=30, value=10, key="m_dork_count")
                
            m_dork_types = st.multiselect(
                "Filter Dork Query Types",
                options=list(DORK_PATTERNS.keys()),
                default=list(DORK_PATTERNS.keys()),
                format_func=lambda x: x.replace("_", " ").title()
            )
            
            with st.expander("⚙️ Manual Exclusions Settings"):
                m_excl_dir = st.toggle("Exclude listing directories (Yelp, Justdial, Yell, etc.)", value=True, key="m_excl_dir")
                m_excl_jobs = st.toggle("Exclude career postings, news, blogs, and PDFs", value=True, key="m_excl_jobs")

            if st.button("Generate Dorks", type="primary", use_container_width=True, key="m_gen_btn"):
                with st.spinner("⚡ Compiling dork search syntaxes..."):
                    manual_config = {
                        "country": m_country,
                        "state": m_state,
                        "region": m_region,
                        "category": m_category,
                        "sub_category": m_subcategory,
                        "target_service": m_service,
                        "num_dorks": m_dork_count,
                        "dork_types": m_dork_types,
                        "include_keywords": m_inc_kw,
                        "exclude_keywords": m_exc_kw,
                        "exclude_directories": m_excl_dir,
                        "exclude_jobs_blogs_news": m_excl_jobs
                    }
                    
                    try:
                        manual_dorks = service.generate_manual_dorks(manual_config)
                        st.session_state["manual_dorks_result"] = manual_dorks
                        st.success(f"Successfully compiled {len(manual_dorks)} advanced Google dorks.")
                    except Exception as e:
                        st.error(f"Failed to generate manual dorks: {e}")
                        
            # Render manual dorks list
            manual_dorks = st.session_state.get("manual_dorks_result")
            if manual_dorks:
                st.markdown("---")
                st.markdown("### 📋 Compiled Google Dorks")
                
                m_dork_data = []
                for idx, d in enumerate(manual_dorks):
                    m_dork_data.append({
                        "Select": True,
                        "Dork ID": d.id,
                        "Dork Query": d.dork,
                        "Type": d.dork_type.replace("_", " ").title(),
                        "Quality": f"⭐ {d.quality_score}",
                        "Copy": d.dork
                    })
                    
                df_m = pd.DataFrame(m_dork_data)
                df_m["Select"] = df_m["Select"].astype(bool)
                df_m = make_dataframe_arrow_compatible(df_m)
                
                edited_df_m = st.data_editor(
                    df_m,
                    hide_index=True,
                    key="manual_dorks_editor",
                    column_config={
                        "Select": st.column_config.CheckboxColumn("Select", default=True),
                        "Dork ID": st.column_config.TextColumn("Dork ID", disabled=True),
                        "Dork Query": st.column_config.TextColumn("Dork Query", disabled=True),
                        "Type": st.column_config.TextColumn("Type", disabled=True),
                        "Quality": st.column_config.TextColumn("Quality", disabled=True),
                        "Copy": st.column_config.TextColumn("Copy", disabled=False),
                    }
                )
                
                selected_m_dork_ids = edited_df_m[edited_df_m["Select"] == True]["Dork ID"].tolist()
                selected_m_dorks = edited_df_m[edited_df_m["Select"] == True]["Dork Query"].tolist()
                
                st.markdown("##### ⚙️ Dork Optimizer Actions")
                
                ac_col1, ac_col2 = st.columns(2)
                
                with ac_col1:
                    # Select campaign
                    st.markdown("##### ⚙️ Target Campaign Selection")
                    if st.session_state.get("newly_created_campaign_id"):
                        campaigns = campaign_repo.get_all() or []
                        
                    if campaigns:
                        default_index = 0
                        new_id = st.session_state.get("newly_created_campaign_id")
                        if new_id:
                            for i, c in enumerate(campaigns):
                                if c.id == new_id:
                                    default_index = i
                                    break
                                    
                        m_selected_camp = st.selectbox(
                            "Select Scraper Campaign",
                            options=[c.id for c in campaigns],
                            format_func=lambda x: next(c.campaign_name for c in campaigns if c.id == x),
                            index=default_index,
                            key="manual_target_camp"
                        )
                        
                        if st.button("➕ Create New Campaign", key="m_create_btn"):
                            create_campaign_modal(db)
                            
                        sub_c1, sub_c2 = st.columns(2)
                        with sub_c1:
                            if st.button("Send Selected to Scraper", key="send_sel_scraper_btn", use_container_width=True, type="primary"):
                                if not selected_m_dork_ids:
                                    st.warning("Please select at least one dork query.")
                                else:
                                    with st.spinner("Pushing job to database worker..."):
                                        m_res = service.send_dorks_to_scraper(selected_m_dork_ids, m_selected_camp)
                                        st.success(f"🚀 Scraping Job {m_res['job_id']} queued! The background worker will pick it up automatically within 5 seconds. Leads will automatically flow to CRM and MailForge.")
                        with sub_c2:
                            if st.button("Send All to Scraper", key="send_all_scraper_btn", use_container_width=True, type="secondary"):
                                all_dork_ids = [d.id for d in manual_dorks]
                                with st.spinner("Pushing all queries to scraper..."):
                                    m_res = service.send_dorks_to_scraper(all_dork_ids, m_selected_camp)
                                    st.success(f"🚀 Scraping Job {m_res['job_id']} queued! The background worker will pick it up automatically within 5 seconds. Leads will automatically flow to CRM and MailForge.")
                    else:
                        st.info("No campaigns exist. Create one to continue.")
                        if st.button("➕ Create New Campaign", key="m_create_btn_empty"):
                            create_campaign_modal(db)
                        
                with ac_col2:
                    st.write("") # Spacing
                    st.write("") # Spacing
                    if st.button("Save Selected Dorks to History", key="save_dorks_history_btn", use_container_width=True):
                        if not selected_m_dork_ids:
                            st.warning("Please select dorks to save.")
                        else:
                            for d_id in selected_m_dork_ids:
                                d_rec = db.query(GeneratedDork).filter(GeneratedDork.id == d_id).first()
                                if d_rec:
                                    d_rec.status = "saved"
                            db.commit()
                            st.success(f"Saved {len(selected_m_dork_ids)} selected dorks to local database history!")
                            
                    st.info("💡 Hint: After scraping, generated leads are automatically checked for quality, enrichment details, and will become fully available inside the CRM and MailForge Outreach Suite.")
                    
        # ----------------------------------------------------
        # TAB 3: DORK INTELLIGENCE DASHBOARD
        # ----------------------------------------------------
        with tab3:
            from modules.ui.dork_intelligence_ui import render_dork_intelligence_dashboard
            render_dork_intelligence_dashboard()
                    
    except Exception as e:
        logger.error(f"Error rendering Dork Optimizer UI: {e}", exc_info=True)
        st.error(f"⚠️ An error occurred while loading Dork Optimizer: {str(e)}")
        with st.expander("🔍 Show technical details for debugging"):
            st.exception(e)
    finally:
        db.close()
