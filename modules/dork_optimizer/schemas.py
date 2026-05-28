from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class DorkOpportunitySchema(BaseModel):
    country: Optional[str] = None
    state: Optional[str] = None
    region: Optional[str] = None
    category: str
    trend_summary: str
    opportunity_reason: str
    suggested_offer: str
    target_service: str
    score: int = Field(default=0, ge=0, le=100)
    source_articles: List[Dict[str, Any]] = Field(default_factory=list)

class GeneratedDorkSchema(BaseModel):
    dork: str
    dork_type: str  # business_discovery, contact_page, email_discovery, phone_whatsapp, low_digital_presence, service_need
    intent: str
    quality_score: int = Field(default=0, ge=0, le=100)
    country: Optional[str] = None
    region: Optional[str] = None
    category: Optional[str] = None
    target_service: Optional[str] = None
