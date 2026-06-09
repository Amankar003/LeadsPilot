import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Helper to fetch environment variables seamlessly from Streamlit Cloud Secrets and local .env
def get_env_var(key: str, default=None):
    try:
        import streamlit as st
        # Streamlit Cloud injects secrets into st.secrets
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        # If we are running in a background job or streamlit is not imported properly
        pass
    return os.getenv(key, default)

# Database settings
_db_url = get_env_var("DATABASE_URL", "sqlite:///leadpilot.db")
if _db_url and _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)
DATABASE_URL = _db_url

# API Keys
GROQ_API_KEY = get_env_var("GROQ_API_KEY", "")
GROQ_MODEL = get_env_var("GROQ_MODEL", "llama-3.1-8b-instant")
SERPER_API_KEY = get_env_var("SERPER_API_KEY", "")
SERP_API_KEY = get_env_var("SERP_API_KEY", "")
NEWSDATA_API_KEY = get_env_var("NEWSDATA_API_KEY", "")

# Authentication Settings
ADMIN_EMAIL = get_env_var("ADMIN_EMAIL", "admin@leadpilot.ai")
ADMIN_PASSWORD = get_env_var("ADMIN_PASSWORD", "admin123")

# Outreach Configuration (Agency Info)
SENDER_NAME = get_env_var("SENDER_NAME", "Deepak Kishor")
SENDER_ROLE = get_env_var("SENDER_ROLE", "Founder & Lead Strategist")
AGENCY_WEBSITE = get_env_var("AGENCY_WEBSITE", "3fitech.com")

# SMTP Settings for Email Sender
SMTP_SERVER = get_env_var("SMTP_SERVER", get_env_var("SMTP_HOST", "smtp.gmail.com"))
SMTP_PORT = int(get_env_var("SMTP_PORT", 587))
SMTP_USER = get_env_var("SMTP_USER", get_env_var("SMTP_USERNAME", ""))
SMTP_PASSWORD = get_env_var("SMTP_PASSWORD", "")
DEFAULT_SENDER_EMAIL = get_env_var("DEFAULT_SENDER_EMAIL", "")
DEFAULT_SENDER_NAME = get_env_var("DEFAULT_SENDER_NAME", "")

# App Constants
APP_NAME = "LeadPilot AI"
VERSION = "1.0.0"

# MailForge / SMTP Defaults
MAILFORGE_SECRET_KEY = get_env_var("MAILFORGE_ENCRYPTION_KEY", get_env_var("MAILFORGE_SECRET_KEY", ""))
DEFAULT_SMTP_HOST = get_env_var("DEFAULT_SMTP_HOST", "smtp.gmail.com")
DEFAULT_SMTP_PORT = int(get_env_var("DEFAULT_SMTP_PORT", 587))
DEFAULT_SMTP_USE_TLS = str(get_env_var("DEFAULT_SMTP_USE_TLS", "true")).lower() == "true"

# Outreach Limits
DEFAULT_EMAIL_DELAY_SECONDS = int(get_env_var("DEFAULT_EMAIL_DELAY_SECONDS", 30))
MAX_EMAILS_PER_RUN = int(get_env_var("MAX_EMAILS_PER_RUN", 20))
MAX_FOLLOWUPS = int(get_env_var("MAX_FOLLOWUPS", 2))

# Database Pooling & Serverless
DB_USE_NULL_POOL = str(get_env_var("DB_USE_NULL_POOL", "")).lower() in ("1", "true", "yes")
DB_SERVERLESS = str(get_env_var("DB_SERVERLESS", "")).lower() in ("1", "true", "yes")
DB_POOL_SIZE = int(get_env_var("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(get_env_var("DB_MAX_OVERFLOW", "0"))
DB_POOL_TIMEOUT = int(get_env_var("DB_POOL_TIMEOUT", "30"))

# Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
EXPORTS_DIR = os.path.join(DATA_DIR, "exports")

# Ensure directories exist
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)
