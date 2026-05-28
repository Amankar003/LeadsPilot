def test_imports():
    # Verify all core modules import successfully
    import app
    import config.database
    import config.settings
    import utils.hash_utils
    import modules.ai.email_generator
    import modules.database.models
    import modules.database.repositories
    import modules.jobs.scraping_planner
    import modules.scraping.bulk_serper_runner
    import modules.scraping.google_email_scraper
    import modules.mailforge
    
    assert True
