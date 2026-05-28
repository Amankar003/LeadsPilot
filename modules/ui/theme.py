"""
Shared UI theme, CSS, and helper functions for LeadPilot AI.
"""
import streamlit as st


def inject_custom_css():
    """Inject the global premium CSS theme."""
    st.markdown("""
    <style>
    /* ─── Import Google Font ─── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    /* ─── Global ─── */
    html, body, [class*="css"], .stApp {
        font-family: 'Inter', sans-serif;
    }

    /* ─── Sidebar ─── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f0f23 0%, #1a1a3e 50%, #0f0f23 100%);
    }
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3,
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown span,
    section[data-testid="stSidebar"] label {
        color: #e0e0f0 !important;
    }
    section[data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.1) !important;
    }

    /* ─── Metric Cards ─── */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #667eea11 0%, #764ba211 100%);
        border: 1px solid rgba(102, 126, 234, 0.15);
        border-radius: 12px;
        padding: 16px 20px;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.12);
    }
    div[data-testid="stMetric"] label {
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        letter-spacing: 0.02em;
        opacity: 0.8;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        font-size: 2rem !important;
        font-weight: 800 !important;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    /* ─── Page Headers ─── */
    .page-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 28px 32px;
        border-radius: 16px;
        margin-bottom: 28px;
        color: white;
        position: relative;
        overflow: hidden;
    }
    .page-header::after {
        content: '';
        position: absolute;
        top: -50%;
        right: -20%;
        width: 300px;
        height: 300px;
        background: rgba(255,255,255,0.05);
        border-radius: 50%;
    }
    .page-header h1 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: 700;
        color: white !important;
    }
    .page-header p {
        margin: 6px 0 0 0;
        opacity: 0.85;
        font-size: 0.95rem;
    }

    /* ─── Info Cards ─── */
    .info-card {
        background: linear-gradient(135deg, #f8f9ff 0%, #f0f2ff 100%);
        border: 1px solid rgba(102, 126, 234, 0.12);
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 16px;
    }
    .info-card h3 {
        margin: 0 0 8px 0;
        font-size: 1rem;
        font-weight: 600;
        color: #333;
    }
    .info-card p {
        margin: 0;
        font-size: 0.9rem;
        color: #666;
    }

    /* ─── Status Badges ─── */
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.03em;
    }
    .badge-hot { background: #ff4d4f22; color: #cf1322; border: 1px solid #ff4d4f44; }
    .badge-warm { background: #fa8c1622; color: #d46b08; border: 1px solid #fa8c1644; }
    .badge-cold { background: #1890ff22; color: #096dd9; border: 1px solid #1890ff44; }
    .badge-low { background: #d9d9d922; color: #8c8c8c; border: 1px solid #d9d9d944; }
    .badge-sent { background: #52c41a22; color: #389e0d; border: 1px solid #52c41a44; }
    .badge-failed { background: #ff4d4f22; color: #cf1322; border: 1px solid #ff4d4f44; }
    .badge-draft { background: #faad1422; color: #d48806; border: 1px solid #faad1444; }
    .badge-approved { background: #1890ff22; color: #096dd9; border: 1px solid #1890ff44; }
    .badge-pending { background: #722ed122; color: #531dab; border: 1px solid #722ed144; }

    /* ─── Workflow Steps ─── */
    .workflow-step {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: linear-gradient(135deg, #667eea11 0%, #764ba211 100%);
        border: 1px solid rgba(102, 126, 234, 0.15);
        border-radius: 10px;
        padding: 10px 16px;
        margin: 4px;
        font-size: 0.85rem;
        font-weight: 500;
    }
    .workflow-step.active {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-color: transparent;
    }
    .workflow-arrow {
        display: inline-block;
        color: #999;
        font-size: 1.2rem;
        margin: 0 4px;
    }

    /* ─── Buttons ─── */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 8px 24px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4) !important;
    }

    /* ─── Expanders ─── */
    .streamlit-expanderHeader {
        font-weight: 600 !important;
        font-size: 0.95rem !important;
    }

    /* ─── Data Editor / Dataframe ─── */
    .stDataFrame, .stDataEditor {
        border-radius: 12px !important;
        overflow: hidden;
    }

    /* ─── Tabs ─── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 8px 20px;
        font-weight: 500;
    }

    /* ─── Progress Bar ─── */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%) !important;
    }

    /* ─── Dividers ─── */
    hr {
        border: none !important;
        height: 1px !important;
        background: linear-gradient(90deg, transparent, rgba(102, 126, 234, 0.2), transparent) !important;
        margin: 24px 0 !important;
    }

    /* ─── Scrollbar ─── */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }
    ::-webkit-scrollbar-track {
        background: transparent;
    }
    ::-webkit-scrollbar-thumb {
        background: rgba(102, 126, 234, 0.3);
        border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(102, 126, 234, 0.5);
    }

    /* ─── Empty State ─── */
    .empty-state {
        text-align: center;
        padding: 48px 24px;
        color: #999;
    }
    .empty-state .icon {
        font-size: 3rem;
        margin-bottom: 12px;
    }
    .empty-state h3 {
        margin: 0 0 8px 0;
        color: #555;
    }
    .empty-state p {
        margin: 0;
        font-size: 0.9rem;
    }
    </style>
    """, unsafe_allow_html=True)


def page_header(icon: str, title: str, subtitle: str = ""):
    """Render a gradient page header with icon."""
    sub_html = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(f"""
    <div class="page-header">
        <h1>{icon} {title}</h1>
        {sub_html}
    </div>
    """, unsafe_allow_html=True)


def status_badge(status: str) -> str:
    """Return HTML for a colored status badge."""
    cls_map = {
        "HOT": "badge-hot", "WARM": "badge-warm", "COLD": "badge-cold", "LOW": "badge-low",
        "SENT": "badge-sent", "FAILED": "badge-failed", "DRAFT": "badge-draft",
        "APPROVED": "badge-approved", "PENDING": "badge-pending", "GENERATED": "badge-pending",
        "COMPLETED": "badge-sent", "RUNNING": "badge-approved",
        "EMAIL_SENT": "badge-sent", "REPLIED": "badge-sent", "MEETING_BOOKED": "badge-approved",
        "CLOSED_WON": "badge-sent", "CLOSED_LOST": "badge-failed",
        "DO_NOT_CONTACT": "badge-failed", "NOT_INTERESTED": "badge-low",
    }
    cls = cls_map.get(status, "badge-draft")
    return f'<span class="badge {cls}">{status}</span>'


def empty_state(icon: str, title: str, message: str):
    """Render a centered empty state message."""
    st.markdown(f"""
    <div class="empty-state">
        <div class="icon">{icon}</div>
        <h3>{title}</h3>
        <p>{message}</p>
    </div>
    """, unsafe_allow_html=True)


def info_card(title: str, content: str):
    """Render an info card."""
    st.markdown(f"""
    <div class="info-card">
        <h3>{title}</h3>
        <p>{content}</p>
    </div>
    """, unsafe_allow_html=True)


def workflow_indicator(steps: list, active_index: int = -1):
    """Render a horizontal workflow step indicator."""
    html_parts = []
    for i, step in enumerate(steps):
        cls = "workflow-step active" if i == active_index else "workflow-step"
        html_parts.append(f'<span class="{cls}">{step}</span>')
        if i < len(steps) - 1:
            html_parts.append('<span class="workflow-arrow">→</span>')
    st.markdown(f'<div style="margin-bottom:20px;">{"".join(html_parts)}</div>', unsafe_allow_html=True)


import pandas as pd

def make_dataframe_arrow_compatible(df: pd.DataFrame) -> pd.DataFrame:
    """Make pandas dataframe compatible with Streamlit Arrow serialization.
    Preserves boolean columns so that st.data_editor CheckboxColumn works correctly.
    """
    if "Page" in df.columns:
        df["Page"] = pd.to_numeric(df["Page"], errors="coerce").fillna(0).astype(int)
    
    # Ensure boolean columns stay as bool (not converted to string)
    bool_cols = [col for col in df.columns if df[col].dtype == 'bool']
    
    for col in df.columns:
        if col in bool_cols:
            continue  # Skip boolean columns — they must stay bool for CheckboxColumn
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str)
            
    return df

def format_lead_data(l):
    """Formats a Lead model instance into a standardized dictionary for UI tables."""
    raw = getattr(l, "raw_data", None) or {}
    return {
        "Name/Business": l.business_name,
        "Email": l.email or "",
        "Phone": l.phone or "",
        "Website": l.website or "",
        "Category": l.category,
        "Page": raw.get("page", raw.get("serp_page", "")),
        "Result URL": raw.get("link", raw.get("result_url", l.website or l.google_maps_url or "")),
        "Created On": l.created_at.strftime("%Y-%m-%d %H:%M") if getattr(l, "created_at", None) else "",
        "Status": l.status,
    }
