import streamlit as st
import pandas as pd
from modules.mailforge.service import MailForgeService
from config.database import SessionLocal
from modules.database.models import MailForgeCampaign, MailForgeLead, MailForgeDraft

def render_generate_emails():
    st.markdown("### 🧠 Generate AI Outreach Sequences")
    st.caption("Generate subject line, opening sentence, cold pitch email body, CTA, and 3 sequential follow-up drafts using campaign intelligence.")
    st.divider()

    db = SessionLocal()
    try:
        campaigns = db.query(MailForgeCampaign).order_by(MailForgeCampaign.created_at.desc()).all()
        if not campaigns:
            st.info("Please create a MailForge campaign first.")
            return

        camp_options = {c.id: c.name for c in campaigns}
        selected_campaign_id = st.selectbox(
            "🎯 Select Outreach Campaign",
            options=list(camp_options.keys()),
            format_func=lambda x: camp_options[x],
            key="gen_select_camp"
        )

        campaign = db.query(MailForgeCampaign).filter(MailForgeCampaign.id == selected_campaign_id).first()

        col1, col2 = st.columns(2)
        with col1:
            st.info(f"📋 **Campaign Tone:** {campaign.tone}\n\n📐 **Target Length:** {campaign.email_length}")
        with col2:
            st.info(f"💼 **Pitch Target:** {campaign.target_service}\n\n🎯 **Goal:** {campaign.goal}")

        # Show pending leads
        leads = db.query(MailForgeLead).filter(
            MailForgeLead.mailforge_campaign_id == selected_campaign_id
        ).all()

        if not leads:
            st.warning("No leads found in this campaign! Please upload leads first.")
            return

        drafts = db.query(MailForgeDraft).filter(
            MailForgeDraft.mailforge_campaign_id == selected_campaign_id
        ).all()
        leads_with_draft = {d.lead_id for d in drafts if d.lead_id}

        pending_leads = [l for l in leads if l.lead_id not in leads_with_draft]

        st.markdown(f"📊 **Campaign Stats:** **{len(leads)}** total leads, **{len(drafts)}** drafts generated, **{len(pending_leads)}** pending generation.")

        if not pending_leads:
            st.success("🎉 All outreach drafts generated for this campaign!")
            return

        st.divider()

        # Selection of leads to generate
        st.markdown("#### 👥 Select Leads for Generation")
        
        lead_rows = []
        for l in pending_leads:
            lead_rows.append({
                "Select": True,
                "Email": l.email,
                "Business Name": l.business_name or "N/A",
                "Website": l.website or "N/A",
                "Status": l.enrichment_status
            })
        
        df_leads = pd.DataFrame(lead_rows)
        # Display table with checkboxes
        edited_df = st.data_editor(
            df_leads,
            column_config={
                "Select": st.column_config.CheckboxColumn(required=True)
            },
            disabled=["Email", "Business Name", "Website", "Status"],
            hide_index=True,
            use_container_width=True
        )

        selected_emails = edited_df[edited_df["Select"]]["Email"].tolist()

        if not selected_emails:
            st.warning("Please select at least one lead to generate emails.")
            return

        if st.button("🧠 Generate AI Cold Email & Follow-ups", type="primary", use_container_width=True):
            progress_bar = st.progress(0.0)
            status_text = st.empty()

            service = MailForgeService()
            
            # Filter pending leads matching selected emails
            target_leads = [l for l in pending_leads if l.email in selected_emails]
            
            success = 0
            failed = 0
            
            for idx, mf_lead in enumerate(target_leads):
                status_text.text(f"Generating AI sequence for {mf_lead.business_name or mf_lead.email}... ({idx+1}/{len(target_leads)})")
                progress_bar.progress((idx + 1) / len(target_leads))

                try:
                    # Formulate lead dictionary for gen
                    lead_dict = {
                        "id": mf_lead.lead_id,
                        "email": mf_lead.email,
                        "business_name": mf_lead.business_name,
                        "website": mf_lead.website,
                        "domain": mf_lead.domain,
                        "category": campaign.target_service
                    }
                    
                    campaign_config = {
                        "tone": campaign.tone,
                        "email_length": campaign.email_length,
                        "goal": campaign.goal,
                        "target_service": campaign.target_service
                    }
                    
                    import json
                    sender_profile = {}
                    if campaign.sender_profile:
                        try:
                            sender_profile = json.loads(campaign.sender_profile)
                        except:
                            pass

                    email_data = service.generator.generate_email(lead_dict, campaign_config, sender_profile)

                    # Save Draft
                    draft = MailForgeDraft(
                        mailforge_campaign_id=selected_campaign_id,
                        lead_id=mf_lead.lead_id,
                        subject=email_data.get("subject", "Connecting"),
                        body=email_data.get("body", ""),
                        opening_line=email_data.get("opening_line", ""),
                        cta=email_data.get("cta", ""),
                        personalization_reason=email_data.get("personalization_reason", ""),
                        confidence_score=json.dumps({"score": email_data.get("confidence_score", 0.5)}),
                        status="draft",
                        version=1
                    )
                    db.add(draft)
                    db.flush()

                    # Save Followups
                    service.followup_service.create_followups_for_draft(draft.id, email_data.get("followups", []))
                    
                    mf_lead.status = "GENERATED"
                    success += 1
                except Exception as e:
                    logger.error(f"Failed to generate outreach for {mf_lead.email}: {e}")
                    failed += 1

                if idx % 3 == 0:
                    db.commit()

            db.commit()
            st.success(f"🎉 Sequence generation complete! Generated: **{success}** | Failed: **{failed}**")
            st.rerun()

    finally:
        db.close()
