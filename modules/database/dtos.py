class DotDict(dict):
    """
    A dictionary that supports dot notation access.
    This fulfills the requirement for a pure Python dict/list DTO layer,
    while allowing existing UI code (like `lead.business_name`) to continue working
    without massive refactoring.
    """
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(f"'DotDict' object has no attribute '{item}'")

    def __setattr__(self, key, value):
        self[key] = value

def lead_to_dto(lead) -> DotDict:
    """Convert a SQLAlchemy Lead object and its eager-loaded relations into a DotDict."""
    if not lead:
        return None
        
    dto = DotDict()
    dto.id = lead.id
    dto.business_name = lead.business_name
    dto.email = lead.email
    dto.phone = lead.phone
    dto.website = lead.website
    dto.created_at = lead.created_at
    dto.status = lead.status
    dto.raw_data = lead.raw_data
    dto.scraping_job_id = lead.scraping_job_id
    dto.campaign_id = lead.campaign_id
    dto.category = getattr(lead, 'category', None)
    dto.city = getattr(lead, 'city', None)
    dto.state = getattr(lead, 'state', None)
    dto.country = getattr(lead, 'country', None)
    dto.address = getattr(lead, 'address', None)
    dto.rating = getattr(lead, 'rating', None)
    dto.google_maps_url = getattr(lead, 'google_maps_url', None)
    
    # Preload the campaign_name relationship safely
    dto.campaign = DotDict()
    if hasattr(lead, 'campaign') and lead.campaign:
        dto.campaign.campaign_name = lead.campaign.campaign_name
    else:
        dto.campaign.campaign_name = "Unknown"
        
    return dto

def job_to_dto(job) -> DotDict:
    """Convert a SQLAlchemy ScrapingJob object into a DotDict."""
    if not job:
        return None
        
    dto = DotDict()
    dto.id = job.id
    dto.platform = job.platform
    dto.location = job.location
    dto.status = job.status
    dto.total_loaded = job.total_loaded
    dto.total_scraped = job.total_scraped
    dto.total_saved = job.total_saved
    dto.total_duplicates = job.total_duplicates
    dto.total_skipped = job.total_skipped
    dto.total_failed = job.total_failed
    dto.campaign_id = job.campaign_id
    
    # Preload campaign info safely
    dto.campaign = DotDict()
    if hasattr(job, 'campaign') and job.campaign:
        dto.campaign.campaign_name = job.campaign.campaign_name
    else:
        dto.campaign.campaign_name = "Unknown Campaign"
        
    return dto
