from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from modules.database.models import Base, DorkPipelineRun, DorkOpportunity, GeneratedDork, Campaign, ScrapingJob
from modules.dork_optimizer.news_fetcher import NewsFetcher
from modules.dork_optimizer.trend_analyzer import TrendAnalyzer
from modules.dork_optimizer.opportunity_finder import OpportunityFinder
from modules.dork_optimizer.dork_generator import DorkGenerator
from modules.dork_optimizer.dork_scorer import DorkScorer
from modules.dork_optimizer.dork_filters import is_low_quality_dork_url, calculate_lead_quality_score
from modules.dork_optimizer.service import DorkOptimizerService

def setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()

def test_news_fetcher():
    fetcher = NewsFetcher()
    
    # 1. Test global news
    global_items = fetcher.fetch_global_news(limit=5)
    assert len(global_items) > 0
    assert "title" in global_items[0]
    assert "link" in global_items[0]
    assert "description" in global_items[0]
    
    # 2. Test country specific
    country_items = fetcher.fetch_country_news("UAE", limit=2)
    assert len(country_items) > 0
    assert any("uae" in str(item).lower() for item in country_items)

def test_trend_analyzer():
    analyzer = TrendAnalyzer()
    mock_news = [
        {
            "title": "Dubai real estate brokers migrate to cloud CRM platforms",
            "description": "Property agents in the UAE are automating contact pipelines.",
            "link": "https://example.com/item1"
        }
    ]
    
    trends = analyzer.analyze_trends(mock_news, {"target_service": "CRM Automation"})
    assert len(trends) == 1
    assert trends[0]["category"] == "Real Estate"
    assert trends[0]["country"] == "UAE"
    assert trends[0]["target_service"] == "CRM Automation"

def test_opportunity_finder():
    finder = OpportunityFinder()
    mock_trends = [
        {
            "category": "Real Estate",
            "country": "UAE",
            "state": "Dubai",
            "region": "Dubai Marina",
            "target_service": "CRM Automation",
            "demand_signal": "Inflow tracking problems",
            "trend_reason": "Brokers are struggling to organize customer details.",
            "title": "Dubai brokers CRM trend",
            "link": "https://example.com/trend"
        }
    ]
    
    opps = finder.find_opportunities(mock_trends, {"num_opportunities": 2})
    assert len(opps) == 1
    assert opps[0]["category"] == "Real Estate"
    assert opps[0]["country"] == "UAE"
    assert opps[0]["region"] == "Dubai Marina"
    assert opps[0]["score"] >= 80  # Highly specific region & category should score high
    assert "suggested_offer" in opps[0]

def test_dork_generator():
    generator = DorkGenerator()
    mock_opp = {
        "category": "Healthcare",
        "country": "US",
        "state": "Florida",
        "region": "Miami",
        "target_service": "AI Chatbot",
        "exclude_directories": True,
        "exclude_jobs_blogs_news": True
    }
    
    dorks = generator.generate_from_opportunity(mock_opp, dork_count=5)
    assert len(dorks) == 5
    assert all("site:com" in d["dork"] or "-yelp" in d["dork"] for d in dorks if d["dork_type"] == "contact_page")
    assert all("Healthcare" in d["category"] for d in dorks)
    
    # Test manual generator
    manual_config = {
        "category": "Legal",
        "region": "London",
        "country": "UK",
        "target_service": "SEO",
        "num_dorks": 3,
        "include_keywords": "injury",
        "exclude_keywords": "family",
        "exclude_directories": True,
        "exclude_jobs_blogs_news": True
    }
    m_dorks = generator.generate_manual(manual_config)
    assert len(m_dorks) == 3
    assert all('"injury"' in d["dork"] for d in m_dorks)
    assert all('-"family"' in d["dork"] for d in m_dorks)
    assert all("-yell" in d["dork"] for d in m_dorks)

def test_dork_scorer():
    scorer = DorkScorer()
    
    dork1 = '"dental clinic" "London" "contact us" -yell -jobs'
    dork2 = "dentist"
    
    score1 = scorer.score_dork(dork1, {})
    score2 = scorer.score_dork(dork2, {})
    
    assert score1 > score2
    assert 0 <= score1 <= 100
    assert 0 <= score2 <= 100

def test_dork_filters():
    # 1. URL Exclusions
    assert is_low_quality_dork_url("https://www.yelp.com/biz/dental-clinic") is True
    assert is_low_quality_dork_url("https://www.indeed.com/jobs?q=dentist") is True
    assert is_low_quality_dork_url("https://example.com/blog/how-to-brush-teeth") is True
    assert is_low_quality_dork_url("https://sweetdental.com/contact-us") is False
    
    # 2. Lead Quality Score
    lead1 = {
        "business_name": "Modern Dental",
        "website": "https://moderndental.com",
        "email": "contact@moderndental.com",
        "phone": "+123456789",
        "category": "Healthcare"
    }
    
    lead2 = {
        "business_name": "Unknown Clinic",
        "website": None,
        "email": None,
        "phone": None
    }
    
    assert calculate_lead_quality_score(lead1) == 100
    assert calculate_lead_quality_score(lead2) <= 15

def test_dork_optimizer_service():
    db = setup_in_memory_db()
    try:
        service = DorkOptimizerService(db)
        
        # 1. Test Run Pipeline
        pipeline_config = {
            "trend_scope": "Global",
            "target_service": "AI Chatbot",
            "num_opportunities": 2,
            "dorks_per_opportunity": 2,
            "exclude_directories": True,
            "exclude_jobs_blogs_news": True
        }
        res = service.run_pipeline(pipeline_config)
        assert res["run_id"] is not None
        assert len(res["opportunities"]) > 0
        assert res["dorks_count"] > 0
        
        # Verify db persistence
        db_run = db.query(DorkPipelineRun).filter(DorkPipelineRun.id == res["run_id"]).first()
        assert db_run is not None
        assert db_run.status == "completed"
        
        opps = db.query(DorkOpportunity).filter(DorkOpportunity.pipeline_run_id == db_run.id).all()
        assert len(opps) == len(res["opportunities"])
        
        # 2. Test Manual Dorks Generation
        manual_config = {
            "country": "US",
            "region": "Miami",
            "category": "Spa",
            "target_service": "SEO",
            "num_dorks": 2,
            "exclude_directories": True,
            "exclude_jobs_blogs_news": True
        }
        m_dorks = service.generate_manual_dorks(manual_config)
        assert len(m_dorks) == 2
        
        # Verify manual run database persistence
        m_run = db.query(GeneratedDork).filter(GeneratedDork.dork_type == m_dorks[0].dork_type).all()
        assert len(m_run) >= 2
        
        # 3. Test send dorks to scraper (mock campaign)
        campaign = Campaign(
            id="test-campaign-123",
            user_id="default-user",
            campaign_name="Test Campaign",
            platform="serper_bulk",
            category="Test",
            location="Miami",
            status="PENDING"
        )
        db.add(campaign)
        db.commit()
        
        dork_ids = [d.id for d in m_dorks]
        scraper_res = service.send_dorks_to_scraper(dork_ids, "test-campaign-123")
        assert scraper_res["status"] == "success"
        assert scraper_res["dorks_count"] == 2
        
        # Verify ScrapingJob is created
        job = db.query(ScrapingJob).filter(ScrapingJob.id == scraper_res["job_id"]).first()
        assert job is not None
        assert job.status == "PENDING"
        assert len(job.category.split("\n")) == 2
        
    finally:
        db.close()
