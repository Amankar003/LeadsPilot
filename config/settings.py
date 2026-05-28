import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database settings
_db_url = os.getenv("DATABASE_URL", "sqlite:///leadpilot.db")
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)
DATABASE_URL = _db_url

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SERP_API_KEY = os.getenv("SERP_API_KEY", "")
# SMTP Settings for Email Sender
SMTP_SERVER = os.getenv("SMTP_SERVER", os.getenv("SMTP_HOST", "smtp.gmail.com"))
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", os.getenv("SMTP_USERNAME", ""))
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
DEFAULT_SENDER_EMAIL = os.getenv("DEFAULT_SENDER_EMAIL", "")
DEFAULT_SENDER_NAME = os.getenv("DEFAULT_SENDER_NAME", "")

# App Constants
APP_NAME = "LeadPilot AI"
VERSION = "1.0.0"

# MailForge / SMTP Defaults
MAILFORGE_SECRET_KEY = os.getenv("MAILFORGE_ENCRYPTION_KEY", os.getenv("MAILFORGE_SECRET_KEY", ""))
DEFAULT_SMTP_HOST = os.getenv("DEFAULT_SMTP_HOST", "smtp.gmail.com")
DEFAULT_SMTP_PORT = int(os.getenv("DEFAULT_SMTP_PORT", 587))
DEFAULT_SMTP_USE_TLS = str(os.getenv("DEFAULT_SMTP_USE_TLS", "true")).lower() == "true"

# Outreach Limits
DEFAULT_EMAIL_DELAY_SECONDS = int(os.getenv("DEFAULT_EMAIL_DELAY_SECONDS", 30))
MAX_EMAILS_PER_RUN = int(os.getenv("MAX_EMAILS_PER_RUN", 20))
MAX_FOLLOWUPS = int(os.getenv("MAX_FOLLOWUPS", 2))

# Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
EXPORTS_DIR = os.path.join(DATA_DIR, "exports")

# Ensure directories exist
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)
