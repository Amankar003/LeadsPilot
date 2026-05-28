import logging
from datetime import datetime
from sqlalchemy.orm import Session
from modules.database.models import (
    ScrapingJob, DorkPipelineRun, DorkOpportunity, GeneratedDork, Campaign
)
from modules.dork_optimizer.news_fetcher import NewsFetcher
from modules.dork_optimizer.trend_analyzer import TrendAnalyzer
from modules.dork_optimizer.opportunity_finder import OpportunityFinder
from modules.dork_optimizer.dork_generator import DorkGenerator
from modules.database.repositories import JobRepository

logger = logging.getLogger(__name__)

class DorkOptimizerService:
    def __init__(self, db: Session):
        self.db = db
        self.fetcher = NewsFetcher()
        self.analyzer = TrendAnalyzer()
        self.finder = OpportunityFinder()
        self.generator = DorkGenerator()
        self.job_repo = JobRepository(db)

    def run_pipeline(self, config: dict) -> dict:
        """
        Runs the full B2B Opportunity Discovery Pipeline:
        1. Fetch trends/news
        2. Analyze trend signals
        3. Identify market opportunities
        4. Compile advanced search dorks for each opportunity
        5. Score and save all records to SQLite/Supabase
        """
        logger.info("Executing Dork Optimizer Trend Pipeline...")
        
        trend_scope = config.get("trend_scope", "Global")
        country = config.get("country", "")
        category = config.get("category", "")
        
        # 1. Create a Pipeline Run record
        run = DorkPipelineRun(
            run_type="auto",
            scope=trend_scope,
            country=country if country else None,
            state=config.get("state"),
            region=config.get("region"),
            category=category if category else None,
            target_service=config.get("target_service"),
            status="running",
            raw_config=config,
            created_at=datetime.utcnow()
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        
        try:
            # 2. Fetch news
            if trend_scope == "Specific Country" and country:
                news = self.fetcher.fetch_country_news(country, limit=30)
            elif trend_scope == "Specific Category" and category:
                news = self.fetcher.fetch_category_news(category, limit=30)
            else:
                news = self.fetcher.fetch_global_news(limit=30)
                
            # 3. Analyze trends
            trends = self.analyzer.analyze_trends(news, config)
            
            # 4. Find opportunities
            opps_data = self.finder.find_opportunities(trends, config)
            
            opps_saved = []
            dorks_saved_count = 0
            
            # 5. Save opportunities & generate dorks
            for opp_data in opps_data:
                opp = DorkOpportunity(
                    pipeline_run_id=run.id,
                    country=opp_data["country"],
                    state=opp_data["state"],
                    region=opp_data["region"],
                    category=opp_data["category"],
                    target_service=opp_data.get("target_service"),
                    trend_summary=opp_data["trend_summary"],
                    opportunity_reason=opp_data["opportunity_reason"],
                    suggested_offer=opp_data["suggested_offer"],
                    score=opp_data["score"],
                    source_articles=opp_data["source_articles"],
                    created_at=datetime.utcnow()
                )
                self.db.add(opp)
                self.db.commit()
                self.db.refresh(opp)
                opps_saved.append(opp)
                
                # Generate and save dorks for this opportunity
                dork_limit = config.get("dorks_per_opportunity", 5)
                # Propagate directory exclusions
                opp_opp_data = opp_data.copy()
                opp_opp_data["exclude_directories"] = config.get("exclude_directories", True)
                opp_opp_data["exclude_jobs_blogs_news"] = config.get("exclude_jobs_blogs_news", True)
                
                opp_dorks = self.generator.generate_from_opportunity(opp_opp_data, dork_limit)
                
                for d_data in opp_dorks:
                    dork_obj = GeneratedDork(
                        pipeline_run_id=run.id,
                        opportunity_id=opp.id,
                        dork=d_data["dork"],
                        dork_type=d_data["dork_type"],
                        quality_score=d_data["quality_score"],
                        intent=d_data["intent"],
                        country=opp.country,
                        state=opp.state,
                        region=opp.region,
                        category=opp.category,
                        target_service=opp_data.get("target_service"),
                        status="draft",
                        created_at=datetime.utcnow()
                    )
                    self.db.add(dork_obj)
                    dorks_saved_count += 1
                    
            # 6. Mark run as completed
            run.status = "completed"
            run.completed_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Pipeline run completed successfully. Saved {len(opps_saved)} opportunities and {dorks_saved_count} dorks.")
            return {
                "run_id": run.id,
                "opportunities": opps_saved,
                "dorks_count": dorks_saved_count
            }
            
        except Exception as e:
            self.db.rollback()
            run.status = "failed"
            self.db.commit()
            logger.error(f"Dork Optimizer Trend Pipeline failed: {e}", exc_info=True)
            raise e

    def generate_manual_dorks(self, config: dict) -> list:
        """
        Runs Manual Generator Mode:
        1. Generates syntactic Google dorks based on form inputs.
        2. Scores and saves them in the database for tracking.
        3. Returns the list of saved GeneratedDork models.
        """
        logger.info("Executing Dork Optimizer Manual Generator...")
        
        # Create manual run
        run = DorkPipelineRun(
            run_type="manual",
            scope="Manual Settings",
            country=config.get("country"),
            state=config.get("state"),
            region=config.get("region"),
            category=config.get("category"),
            target_service=config.get("target_service"),
            status="completed",
            raw_config=config,
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        
        try:
            dorks_data = self.generator.generate_manual(config)
            saved_dorks = []
            
            for d_data in dorks_data:
                dork_obj = GeneratedDork(
                    pipeline_run_id=run.id,
                    opportunity_id=None,
                    dork=d_data["dork"],
                    dork_type=d_data["dork_type"],
                    quality_score=d_data["quality_score"],
                    intent=d_data["intent"],
                    country=config.get("country"),
                    state=config.get("state"),
                    region=config.get("region") or config.get("state"),
                    category=config.get("category"),
                    target_service=config.get("target_service"),
                    status="draft",
                    created_at=datetime.utcnow()
                )
                self.db.add(dork_obj)
                saved_dorks.append(dork_obj)
                
            self.db.commit()
            for d in saved_dorks:
                self.db.refresh(d)
                
            logger.info(f"Manual generation completed. Saved {len(saved_dorks)} dorks.")
            return saved_dorks
            
        except Exception as e:
            self.db.rollback()
            run.status = "failed"
            self.db.commit()
            logger.error(f"Dork Optimizer Manual Generator failed: {e}", exc_info=True)
            raise e

    def save_dorks(self, dorks: list, pipeline_run_id: str = None) -> list:
        """
        Utility database save method.
        """
        saved = []
        for d_data in dorks:
            d = GeneratedDork(
                pipeline_run_id=pipeline_run_id,
                dork=d_data["dork"],
                dork_type=d_data.get("dork_type", "business_discovery"),
                quality_score=d_data.get("quality_score", 70),
                intent=d_data.get("intent", ""),
                country=d_data.get("country"),
                state=d_data.get("state"),
                region=d_data.get("region"),
                category=d_data.get("category"),
                target_service=d_data.get("target_service"),
                status="saved",
                created_at=datetime.utcnow()
            )
            self.db.add(d)
            saved.append(d)
        self.db.commit()
        return saved

    def send_dorks_to_scraper(self, dork_ids: list, campaign_id: str, platform: str = "serper_bulk") -> dict:
        """
        Core Connection Flow: Dork Optimizer -> Scraping Jobs -> Leads
        Creates a pending ScrapingJob for selected dorks.
        This triggers the background worker loop.
        """
        logger.info(f"Pushed {len(dork_ids)} selected dorks to campaign {campaign_id}...")
        
        campaign = self.db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found.")
            
        # 1. Fetch selected dorks
        dorks = self.db.query(GeneratedDork).filter(GeneratedDork.id.in_(dork_ids)).all()
        if not dorks:
            raise ValueError("No selected dorks found.")
            
        # 2. Compile query list (newline-joined string of dorks)
        dork_queries = []
        for d in dorks:
            dork_queries.append(d.dork)
            d.status = "scraped"
            
        category_queries = "\n".join(dork_queries)
        
        # 3. Create single pending ScrapingJob representing these queries
        # The background worker automatically picks it up and executes each dork!
        job = self.job_repo.create(
            campaign_id=campaign_id,
            platform=platform,
            category=category_queries,
            location=campaign.location or "Global",
            status="PENDING",
            total_scraped=0,
            total_saved=0
        )
        
        self.db.commit()
        logger.info(f"Successfully created pending Scraping Job {job.id} for {len(dorks)} dorks.")
        
        return {
            "status": "success",
            "job_id": job.id,
            "dorks_count": len(dorks)
        }
