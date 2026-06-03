"""
Seed Source — Demo fallback data.
Used ONLY when all live sources return zero data.
Always marked as status='demo', never 'ready'.
"""


def fetch_seed_data() -> list[dict]:
    """Return demo seed data. Always marked source_type='seed'."""
    return [
        {
            "source_name": "Seed",
            "source_type": "seed",
            "title": "Ayodhya Pilgrim Tourism Spikes Under New Infrastructure Allocation",
            "url": "",
            "raw_text": "Massive influx of pilgrims and tourists in Ayodhya has created critical bottlenecks in hospitality booking systems, local guide coordination, and Google Business visibility for Tier-2 local agencies.",
            "country": "India",
            "region": "Ayodhya",
            "keyword": "tourism",
            "published_at": "2026-05-01",
        },
        {
            "source_name": "Seed",
            "source_type": "seed",
            "title": "Dubai Land Department Updates Investor Visa Rule",
            "url": "",
            "raw_text": "The Dubai Land Department updated residence visa regulations for real estate investors. The minimum property value of AED 750,000 for the two-year investor visa has been removed for sole owners. Real estate brokerage agencies struggle with high volumes of incoming lead inquiries.",
            "country": "UAE",
            "region": "Dubai",
            "keyword": "real estate",
            "published_at": "2026-05-01",
        },
        {
            "source_name": "Seed",
            "source_type": "seed",
            "title": "Saudi Arabia Cabinet Declares 2026 Year of AI",
            "url": "",
            "raw_text": "The Saudi Cabinet declared 2026 the Year of Artificial Intelligence to scale production-grade AI tools across the private sector. 66% of Saudi consumers actively use AI tools.",
            "country": "Saudi Arabia",
            "region": "Riyadh",
            "keyword": "ai digital transformation",
            "published_at": "2026-05-01",
        },
        {
            "source_name": "Seed",
            "source_type": "seed",
            "title": "Jaipur Heritage Wedding Planners Booking Boom",
            "url": "",
            "raw_text": "Inquiries for luxury heritage weddings in Rajasthan hit historic highs. Wedding planners, caterers, resorts, and local photographers suffer from poor inquiry capture and booking automation.",
            "country": "India",
            "region": "Jaipur",
            "keyword": "wedding events",
            "published_at": "2026-05-01",
        },
        {
            "source_name": "Seed",
            "source_type": "seed",
            "title": "Gold Coast Australia Tourism Recovery Surge",
            "url": "",
            "raw_text": "Gold Coast tourism operators report record bookings. Hotels, tour operators, and local service businesses need online booking systems and Google Business optimization.",
            "country": "Australia",
            "region": "Gold Coast",
            "keyword": "tourism",
            "published_at": "2026-05-01",
        },
    ]
