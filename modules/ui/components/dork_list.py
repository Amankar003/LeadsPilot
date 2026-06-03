import streamlit as st
import pandas as pd
from modules.ui.theme import make_dataframe_arrow_compatible

def render_dork_list(dorks: list, opp_id: str) -> list:
    """
    Renders a clean list of generated dorks, allows selection, and provides a master copy block.
    
    Args:
        dorks: List of dork objects (must have id, dork, dork_type, quality_score) or dicts.
        opp_id: Unique identifier string to namespace Streamlit keys.
        
    Returns:
        List of selected dork IDs.
    """
    if not dorks:
        st.write("No dorks compiled for this opportunity.")
        return []

    st.markdown("##### 📋 Generated Dorks")
    
    dork_data = []
    for i, d in enumerate(dorks):
        if isinstance(d, str):
            d_id = f"str_{i}"
            d_query = d
            d_type = "search"
            d_score = 85
        else:
            # Handle both dicts and SQLAlchemy models
            d_id = d.id if hasattr(d, 'id') else d.get('id', f"dict_{i}")
            d_query = d.dork if hasattr(d, 'dork') else d.get('dork', d.get('Dork', ''))
            d_type = d.dork_type if hasattr(d, 'dork_type') else d.get('dork_type', 'search')
            d_score = d.quality_score if hasattr(d, 'quality_score') else d.get('quality_score', 85)
            
        dork_data.append({
            "Select": True,
            "Dork ID": d_id,
            "Dork Query": d_query,
            "Type": str(d_type).replace("_", " ").title(),
            "Quality": f"⭐ {d_score}"
        })
        
    df_opp = pd.DataFrame(dork_data)
    df_opp["Select"] = df_opp["Select"].astype(bool)
    df_opp = make_dataframe_arrow_compatible(df_opp)
    
    edited_df = st.data_editor(
        df_opp,
        hide_index=True,
        key=f"dork_editor_{opp_id}",
        use_container_width=True,
        column_config={
            "Select": st.column_config.CheckboxColumn("Select", default=True),
            "Dork ID": st.column_config.TextColumn("Dork ID", disabled=True),
            "Dork Query": st.column_config.TextColumn("Dork Query", disabled=True),
            "Type": st.column_config.TextColumn("Type", disabled=True),
            "Quality": st.column_config.TextColumn("Quality", disabled=True),
        }
    )
    
    selected_df = edited_df[edited_df["Select"] == True]
    selected_dork_ids = selected_df["Dork ID"].tolist()
    selected_dork_queries = selected_df["Dork Query"].tolist()
    
    with st.expander("📝 Copy Selected Dorks (One-Click)"):
        st.caption("Hover over the block below and click the copy icon in the top right to copy all selected dorks.")
        all_dorks_text = "\n\n".join(selected_dork_queries)
        st.code(all_dorks_text, language="text")
        
    return selected_dork_ids
