from abc import ABC, abstractmethod

class BaseScraper(ABC):
    
    @abstractmethod
    def scrape(self, query: str, limit: int = None, location: str = None):
        """
        Base scrape method to be implemented by all scrapers.
        Should yield standard lead dictionaries.
        """
        pass
