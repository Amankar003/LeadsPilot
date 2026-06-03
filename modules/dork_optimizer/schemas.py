from pydantic import BaseModel, Field
from typing import List, Optional

class Trend(BaseModel):
    trend_name: str = Field(default="Unknown Trend", description="Short descriptive trend title")
    category: str = Field(default="General", description="Industry or sector category")
    description: str = Field(default="No description provided.", description="Summary of the trend")
    opportunity_score: int = Field(default=50, ge=0, le=100, description="Score from 0-100 indicating opportunity strength")
    business_impact: str = Field(default="Unknown impact", description="How this impacts B2B businesses")
    target_market: str = Field(default="Global", description="The overarching target market")
    
    # Fields kept for OpportunityFinder logic, with safe defaults
    target_service: str = Field(default="Website Development", description="Recommended 3FI service")
    country: str = Field(default="", description="Target country")
    region: str = Field(default="", description="Target city/region")
    
    # Allow fallback for old 'sector' key if LLM hallucinates it instead of 'category'
    sector: Optional[str] = Field(default=None, exclude=True)
    
    def model_post_init(self, __context) -> None:
        if self.sector and self.category == "General":
            self.category = self.sector

class TrendList(BaseModel):
    trends: List[Trend] = Field(default_factory=list)
