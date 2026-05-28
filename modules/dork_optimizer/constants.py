# Target B2B Services available for pitches
TARGET_SERVICES = [
    "Website Development",
    "SEO",
    "AI Chatbot",
    "Lead Generation",
    "CRM Automation",
    "WhatsApp Automation",
    "Email Outreach",
    "Social Media Automation"
]

# Google Dork syntactic patterns by type
DORK_PATTERNS = {
    "business_discovery": [
        '"{category}" "{region}" "contact"',
        '"{category}" "{region}" "website"',
        '"{category}" "{region}" "company"'
    ],
    "contact_page": [
        'site:{country_tld} "{category}" "{region}" "contact us"',
        '"{category}" "{region}" "contact" "email"'
    ],
    "email_discovery": [
        '"{category}" "{region}" "info@"',
        '"{category}" "{region}" "contact@"',
        '"{category}" "{region}" "email"'
    ],
    "phone_whatsapp": [
        '"{category}" "{region}" "WhatsApp"',
        '"{category}" "{region}" "call us"',
        '"{category}" "{region}" "phone"'
    ],
    "low_digital_presence": [
        '"{category}" "{region}" "business" -facebook -instagram -linkedin',
        '"{category}" "{region}" "contact" -directory -jobs -blog'
    ],
    "service_need": [
        '"{category}" "{region}" "book appointment"',
        '"{category}" "{region}" "get quote"',
        '"{category}" "{region}" "services"'
    ]
}

# Standard Google Dork negative filters to exclude noise
GLOBAL_NEGATIVE_FILTERS = [
    "-jobs", "-career", "-hiring", "-news", "-blog", "-pdf", "-wikipedia",
    "-youtube", "-facebook", "-instagram", "-linkedin", "-reddit", "-quora"
]

# Country-specific directory listings to blacklist
COUNTRY_DIRECTORIES = {
    "IN": ["-justdial", "-sulekha", "-indiamart", "-tradeindia"],
    "India": ["-justdial", "-sulekha", "-indiamart", "-tradeindia"],
    "UAE": ["-bayut", "-propertyfinder", "-dubizzle"],
    "Dubai": ["-bayut", "-propertyfinder", "-dubizzle"],
    "Abu Dhabi": ["-bayut", "-propertyfinder", "-dubizzle"],
    "US": ["-yelp", "-angi", "-thumbtack"],
    "United States": ["-yelp", "-angi", "-thumbtack"],
    "UK": ["-yell", "-checkatrade", "-trustatrader"],
    "United Kingdom": ["-yell", "-checkatrade", "-trustatrader"]
}

# Country TLD mapping for site searches
COUNTRY_TLDS = {
    "IN": "in",
    "India": "in",
    "US": "com",
    "United States": "com",
    "UK": "co.uk",
    "United Kingdom": "co.uk",
    "AE": "ae",
    "UAE": "ae",
    "CA": "ca",
    "Canada": "ca",
    "AU": "com.au",
    "Australia": "com.au",
    "SG": "com.sg",
    "Singapore": "com.sg"
}
