from celery import Task
from workers.celery_app import celery_app
from database.connection import DatabaseManager
from scraper.spider import VijayPathakScraper, ScrapingConfig
import asyncio
import logging
from typing import Dict, List
import aiohttp
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

class AsyncTask(Task):
    """Base task class for async operations"""
    def __init__(self):
        self.db_manager = None
    async def get_db_manager(self):
        if not self.db_manager:
            self.db_manager = DatabaseManager(
                os.getenv('MONGODB_URL', 'mongodb://mongodb:27017/vijayshreepathak_scraper?authSource=admin'),
                os.getenv('MONGODB_DB', 'vijayshreepathak_scraper')
            )
            await self.db_manager.connect()
        return self.db_manager

@celery_app.task(bind=True, base=AsyncTask)
def scrape_single_page(self, url: str, job_id: str, url_doc: Dict):
    """Scrape a single page (Celery task)"""
    async def _scrape():
        try:
            db_manager = await self.get_db_manager()
            config = ScrapingConfig(
                start_urls=[url],
                allowed_domains=["vijayshreepathak.netlify.app"],
                max_depth=1,
                delay_between_requests=0.5
            )
            scraper = VijayPathakScraper(config, db_manager)
            scraper.current_job_id = job_id
            await scraper.process_single_url(url_doc)
            return {"status": "success", "url": url}
        except Exception as e:
            logger.error(f"Failed to scrape {url}: {e}")
            await scraper.handle_url_error(url_doc, str(e))
            return {"status": "error", "url": url, "error": str(e)}
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_scrape())
    finally:
        loop.close()

@celery_app.task(bind=True, base=AsyncTask)
def validate_links(self, page_id: str):
    """Validate all links in a page"""
    async def _validate():
        try:
            db_manager = await self.get_db_manager()
            from bson import ObjectId
            page = await db_manager.db.pages.find_one({"_id": ObjectId(page_id)})
            if not page:
                return {"status": "error", "message": "Page not found"}
            links = page.get("content", {}).get("structured_data", {}).get("links", [])
            validated_links = []
            async with aiohttp.ClientSession() as session:
                for link in links:
                    try:
                        async with session.head(link["href"], timeout=10) as response:
                            link["status"] = "valid" if response.status < 400 else "broken"
                    except Exception:
                        link["status"] = "broken"
                    validated_links.append(link)
            await db_manager.db.pages.update_one(
                {"_id": ObjectId(page_id)},
                {"$set": {"content.structured_data.links": validated_links}}
            )
            return {"status": "success", "page_id": page_id, "validated": len(validated_links)}
        except Exception as e:
            logger.error(f"Failed to validate links for page {page_id}: {e}")
            return {"status": "error", "page_id": page_id, "error": str(e)}
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_validate())
    finally:
        loop.close()

@celery_app.task(bind=True, base=AsyncTask)
def cleanup_old_data(self, days_old: int = 30):
    """Clean up old scraped data"""
    async def _cleanup():
        try:
            db_manager = await self.get_db_manager()
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            result1 = await db_manager.db.url_queue.delete_many({
                "discovered_at": {"$lt": cutoff_date},
                "status": {"$in": ["completed", "failed"]}
            })
            await db_manager.db.scraping_jobs.update_many(
                {},
                {"$pull": {"errors": {"timestamp": {"$lt": cutoff_date}}}}
            )
            return {
                "status": "success",
                "deleted_queue_entries": result1.deleted_count,
                "cutoff_date": cutoff_date.isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return {"status": "error", "error": str(e)}
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_cleanup())
    finally:
        loop.close() 