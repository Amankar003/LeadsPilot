import logging
from typing import List, Dict, Any
from modules.dork_optimizer.constants import (
    DORK_PATTERNS, GLOBAL_NEGATIVE_FILTERS, COUNTRY_DIRECTORIES, COUNTRY_TLDS
)
from modules.dork_optimizer.dork_scorer import DorkScorer

logger = logging.getLogger(__name__)

class DorkGenerator:
    def __init__(self):
        self.scorer = DorkScorer()

    def _get_country_tld(self, country: str) -> str:
        if not country:
            return "com"
        return COUNTRY_TLDS.get(country, COUNTRY_TLDS.get(country.upper(), "com"))

    def _compile_dork_exclusions(self, country: str, exclude_directories: bool, exclude_jobs_blogs: bool) -> List[str]:
        exclusions = []
        
        # 1. Directory exclusions
        if exclude_directories and country:
            # Match directly or by upper-case key
            direct_excl = COUNTRY_DIRECTORIES.get(country) or COUNTRY_DIRECTORIES.get(country.upper())
            if direct_excl:
                exclusions.extend(direct_excl)
            else:
                # Add default generic directory exclusions
                exclusions.extend(["-directory", "-listings", "-yellowpages"])
                
        # 2. Jobs, blogs, news, wikipedia exclusions
        if exclude_jobs_blogs:
            exclusions.extend(GLOBAL_NEGATIVE_FILTERS)
            
        return exclusions

    def generate_from_opportunity(self, opportunity: Dict[str, Any], dork_count: int = 10) -> List[Dict[str, Any]]:
        """
        Generates advanced Google dorks for B2B local business search from a parsed opportunity.
        """
        category = opportunity.get("category", "Business")
        region = opportunity.get("region") or opportunity.get("state") or "Metropolitan"
        country = opportunity.get("country", "")
        target_service = opportunity.get("target_service", "Lead Generation")
        
        country_tld = self._get_country_tld(country)
        exclusions = self._compile_dork_exclusions(
            country=country,
            exclude_directories=opportunity.get("exclude_directories", True),
            exclude_jobs_blogs=opportunity.get("exclude_jobs_blogs_news", True)
        )
        
        dorks = []
        
        # Loop through B2B dork patterns round-robin style until we hit dork_count
        pattern_keys = list(DORK_PATTERNS.keys())
        dorks_compiled = 0
        
        for idx in range(dork_count):
            p_key = pattern_keys[idx % len(pattern_keys)]
            patterns = DORK_PATTERNS[p_key]
            pattern = patterns[(idx // len(pattern_keys)) % len(patterns)]
            
            # Formulate the query by replacing template parameters
            base_query = pattern.replace("{category}", category).replace("{region}", region).replace("{country_tld}", country_tld)
            
            # Combine exclusions
            dork_query = base_query
            if exclusions:
                dork_query = f"{base_query} {' '.join(exclusions)}"
                
            # Score
            ctx = {"country": country, "region": region, "category": category, "target_service": target_service}
            score = self.scorer.score_dork(dork_query, ctx)
            
            dorks.append({
                "dork": dork_query,
                "dork_type": p_key,
                "intent": f"Identify leads for B2B {target_service} in {region}",
                "quality_score": score,
                "country": country,
                "region": region,
                "category": category,
                "target_service": target_service
            })
            
        return dorks

    def generate_manual(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Compiles custom Google dorks based on explicit user form configurations.
        """
        category = config.get("category", "Business")
        sub_category = config.get("sub_category")
        region = config.get("region") or config.get("state") or "Metropolitan"
        country = config.get("country", "")
        target_service = config.get("target_service", "SEO")
        
        country_tld = self._get_country_tld(country)
        exclude_directories = config.get("exclude_directories", True)
        exclude_jobs_blogs = config.get("exclude_jobs_blogs_news", True)
        
        dork_types = config.get("dork_types", list(DORK_PATTERNS.keys()))
        if not dork_types:
            dork_types = list(DORK_PATTERNS.keys())
            
        limit = config.get("num_dorks", 10)
        
        include_keywords = config.get("include_keywords", "")
        exclude_keywords = config.get("exclude_keywords", "")
        
        exclusions = self._compile_dork_exclusions(country, exclude_directories, exclude_jobs_blogs)
        
        # Add custom negative keyword exclusions
        if exclude_keywords:
            for kw in exclude_keywords.split(","):
                kw = kw.strip()
                if kw:
                    exclusions.append(f'-"{kw}"')
                    
        dorks = []
        dorks_compiled = 0
        
        while len(dorks) < limit:
            # Round-robin over requested dork types
            p_key = dork_types[dorks_compiled % len(dork_types)]
            patterns = DORK_PATTERNS[p_key]
            pattern = patterns[(dorks_compiled // len(dork_types)) % len(patterns)]
            
            # Incorporate sub-category if specified
            search_cat = f"{category} {sub_category}" if sub_category else category
            
            base_query = pattern.replace("{category}", search_cat).replace("{region}", region).replace("{country_tld}", country_tld)
            
            # Incorporate user custom included keywords
            if include_keywords:
                for kw in include_keywords.split(","):
                    kw = kw.strip()
                    if kw:
                        base_query = f'{base_query} "{kw}"'
                        
            # Combine exclusions
            dork_query = base_query
            if exclusions:
                dork_query = f"{base_query} {' '.join(exclusions)}"
                
            # Score
            ctx = {"country": country, "region": region, "category": search_cat, "target_service": target_service}
            score = self.scorer.score_dork(dork_query, ctx)
            
            dorks.append({
                "dork": dork_query,
                "dork_type": p_key,
                "intent": f"Identify leads for B2B {target_service} in {region}",
                "quality_score": score,
                "country": country,
                "region": region,
                "category": search_cat,
                "target_service": target_service
            })
            
            dorks_compiled += 1
            if dorks_compiled > 100:  # Fail-safe break
                break
                
        return dorks[:limit]
