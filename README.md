# LeadPilot AI 🚀

LeadPilot AI is an AI-powered lead generation and business intelligence platform designed to help agencies, freelancers, consultants, and growth teams discover leads, analyze businesses, identify pain points, and generate highly personalized outreach content at scale.

Instead of sending emails directly, LeadPilot AI focuses on generating high-quality business insights and ready-to-use outreach content that can be exported and used in any email marketing platform.

---

# ✨ Key Features

### 🎯 Lead Generation

* Google Maps lead scraping
* Bulk SERP scraping
* Dork Optimizer for targeted lead discovery
* CSV/Excel lead imports
* Campaign-based lead management

### 🧠 AI Business Intelligence

* Website analysis
* Digital presence analysis
* SEO opportunity detection
* Conversion optimization insights
* Trust signal analysis
* Lead qualification
* Service recommendation engine

### 📊 AI Business Audit

For every lead, LeadPilot AI can analyze:

* Website quality
* Contact accessibility
* Local SEO opportunities
* Lead generation opportunities
* Website redesign requirements
* Automation opportunities
* CRM requirements
* Chatbot requirements
* Mobile experience
* Conversion bottlenecks
* Digital presence maturity

### ✉️ AI Outreach Content Generation

Generate personalized:

* Subject lines
* Outreach emails
* Service pitches
* Pain-point-driven messaging
* Business-specific value propositions

### 📁 Campaign-Based CSV Export

Export generated outreach content as CSV:

```csv
receiverid,subject,body
lead1@example.com,Subject Line,Email Content
lead2@example.com,Subject Line,Email Content
```

Compatible with:

* Instantly
* Smartlead
* Apollo
* Brevo
* Mail Merge
* Custom email automation systems

---

# 🏗️ System Architecture

```text
Lead Sources
      ↓
Campaign Management
      ↓
Lead Database
      ↓
Lead Intelligence Engine
      ↓
AI Business Audit
      ↓
Pain Point Detection
      ↓
Personalized Email Generation
      ↓
Campaign-wise CSV Export
```

---

# ⚡ Core Modules

| Module              | Description                              |
| ------------------- | ---------------------------------------- |
| Dashboard           | Central analytics and campaign overview  |
| Dork Optimizer      | AI-assisted lead discovery and targeting |
| Campaign Manager    | Campaign creation and management         |
| Lead Sources        | Scraping and lead acquisition            |
| Lead Enrichment     | Lead validation and enrichment           |
| Lead Intelligence   | Deep business analysis and AI audits     |
| Email Export Engine | Campaign-wise outreach content export    |
| Settings            | API keys and application configuration   |

---

# 🛠️ Tech Stack

### Frontend

* Streamlit

### Backend

* Python

### Database

* SQLite (Development)
* PostgreSQL (Production)

### ORM

* SQLAlchemy

### Scraping

* Playwright
* BeautifulSoup
* HTTPX

### AI Engine

* Groq API
* Llama Models

### Data Processing

* Pandas
* OpenPyXL
* RapidFuzz
* Email Validator
* PhoneNumbers

### Logging

* Loguru

---

# 🚀 Quick Start

## 1. Clone Repository

```bash
git clone <repository-url>
cd leadpilot_ai
```

## 2. Create Virtual Environment

```bash
python -m venv .venv
```

### Windows

```bash
.venv\Scripts\activate
```

### Linux / macOS

```bash
source .venv/bin/activate
```

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## 4. Install Playwright

```bash
playwright install chromium
```

## 5. Configure Environment

Copy:

```bash
copy .env.example .env
```

Update:

```env
DATABASE_URL=sqlite:///leadpilot.db

GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile

SERPER_API_KEY=your_serper_api_key
```

---

# ▶️ Run Application

```bash
streamlit run app.py
```

Application will be available at:

```text
http://localhost:8501
```

---

# 📋 Typical Workflow

## Step 1: Create Campaign

Examples:

* Dentists in London
* Real Estate Agencies in Dubai
* Restaurants in New York
* Marketing Agencies in Australia

---

## Step 2: Collect Leads

Choose:

* Google Maps Scraper
* Bulk SERP Scraper
* Dork Optimizer
* CSV/Excel Import

---

## Step 3: Analyze Leads

Run Lead Intelligence.

The system will automatically:

* Analyze websites
* Detect pain points
* Identify missing opportunities
* Recommend services
* Build outreach strategies

---

## Step 4: Generate Outreach Content

LeadPilot AI creates:

* Personalized subject lines
* Personalized outreach emails
* Service recommendations
* Business-specific pitches

---

## Step 5: Export Campaign CSV

Download:

```csv
receiverid,subject,body
```

for all campaign leads.

---

# 📊 Dashboard Features

Dashboard provides:

* Total campaigns
* Total leads
* Analyzed leads
* Generated emails
* Campaign performance
* Scraping statistics
* Analysis progress

Actions:

* Analyze Campaign Leads
* View Leads
* Download Leads CSV
* Download Generated Email CSV

---

# ⚙️ Environment Variables

```env
DATABASE_URL=
GROQ_API_KEY=
GROQ_MODEL=
SERPER_API_KEY=
```

Optional:

```env
LOG_LEVEL=INFO
MAX_PARALLEL_ANALYSIS=5
```

---

# 🔒 Security

LeadPilot AI:

✅ Does not send emails

✅ Does not store SMTP passwords

✅ Does not require sender accounts

✅ Does not use SendGrid

✅ Does not perform automated outreach

✅ Only generates business intelligence and outreach content

Users remain fully responsible for how exported content is used.

---

# 📈 Recommended Usage

For best results:

* Analyze leads in batches of 20–100
* Review generated outreach before sending
* Validate email addresses before export
* Re-run audits periodically for updated insights

---

# 🤝 Ideal Users

LeadPilot AI is built for:

* Marketing Agencies
* Web Development Agencies
* SaaS Sales Teams
* Freelancers
* Growth Consultants
* Lead Generation Agencies
* Business Development Teams

---

# 📄 License

This project is intended for ethical business intelligence, lead generation, and personalized outreach preparation.

Users are responsible for complying with all applicable laws, regulations, and outreach policies in their jurisdiction.

---

Built with ❤️ using Python, Streamlit, Groq, Playwright, SQLAlchemy, and AI-powered Business Intelligence.
