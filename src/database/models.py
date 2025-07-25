from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, TEXT
from typing import Any

# Pydantic models can be imported from src/api/schemas.py if needed

def create_indexes(db: AsyncIOMotorDatabase):
    """Create all necessary indexes for the collections."""
    # Pages: unique url, text index for search
    db.pages.create_index([('url', ASCENDING)], unique=True)
    db.pages.create_index([('content.content_hash', ASCENDING)])
    db.pages.create_index([('navigation.section', ASCENDING)])
    db.pages.create_index([('navigation.subsection', ASCENDING)])
    db.pages.create_index([('content.clean_text', TEXT), ('title', TEXT), ('search_fields.keywords', TEXT)],
                         name='text_search_index', default_language='english')

    # Scraping jobs: sort by start_time
    db.scraping_jobs.create_index([('start_time', DESCENDING)])
    db.scraping_jobs.create_index([('status', ASCENDING)])

    # URL queue: unique normalized_url per job, status
    db.url_queue.create_index([('normalized_url', ASCENDING), ('job_id', ASCENDING)], unique=True)
    db.url_queue.create_index([('status', ASCENDING)])
    db.url_queue.create_index([('priority', ASCENDING)])
    db.url_queue.create_index([('discovered_at', DESCENDING)])

    # Site structure: domain unique
    db.site_structure.create_index([('domain', ASCENDING)], unique=True)
    db.site_structure.create_index([('last_updated', DESCENDING)])

    # Optionally, add more indexes as needed for performance

# Optionally, add Pydantic models for validation (see src/api/schemas.py for full models) 