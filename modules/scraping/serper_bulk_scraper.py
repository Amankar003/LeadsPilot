import requests
import logging
from typing import List, Dict
from config.settings import SERPER_API_KEY

# Set up logging
logger = logging.getLogger(__name__)

def fetch_serper_results(query: str, page: int = 1, num: int = 10) -> List[Dict]:
    """
    Fetches Google SERP results from Serper.dev API.
    """
    if not SERPER_API_KEY:
        logger.error("SERPER_API_KEY not found in settings or environment.")
        return []

    url = "https://google.serper.dev/search"
    
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "q": query,
        "page": page,
        "num": num,
        "gl": "in",
        "hl": "en"
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        if response.status_code == 401:
            logger.error(f"Invalid Serper API Key. Status: {response.status_code}")
            return []
        
        if response.status_code == 429:
            logger.warning(f"Serper API Rate limit hit. Status: {response.status_code}")
            return []

        response.raise_for_status()
        data = response.json()
        
        if not isinstance(data, dict):
            logger.warning(f"Unexpected response format from Serper. Expected dict, got {type(data)}")
            if isinstance(data, list) and data and isinstance(data[0], dict):
                data = data[0]
            else:
                data = {}
        
        results = []
        organic_results = data.get("organic", [])
        
        for res in organic_results:
            results.append({
                "title": res.get("title", ""),
                "link": res.get("link", ""),
                "snippet": res.get("snippet", ""),
                "position": res.get("position", ""),
                "query": query,
                "page": page,
                "source": "serper"
            })
            
        return results

    except requests.exceptions.Timeout:
        logger.error(f"Timeout while fetching Serper results for query: {query}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Serper results: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in Serper scraper: {str(e)}")
        
    return []
