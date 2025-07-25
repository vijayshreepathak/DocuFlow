import os
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from .models import create_indexes

class DatabaseManager:
    def __init__(self, uri: str = None, db_name: str = None):
        self.uri = uri or os.getenv('MONGODB_URL', 'mongodb://mongodb:27017/')
        self.db_name = db_name or os.getenv('MONGODB_DB', 'vijayshreepathak_scraper')
        print(f"Connecting to MongoDB at: {self.uri}")
        self.client: AsyncIOMotorClient = None
        self.db: AsyncIOMotorDatabase = None

    async def connect(self):
        self.client = AsyncIOMotorClient(self.uri)
        self.db = self.client[self.db_name]
        # Create indexes (non-blocking, fire-and-forget)
        create_indexes(self.db)

    async def close(self):
        if self.client:
            self.client.close()

    # Expose collection handles for convenience
    @property
    def pages(self):
        return self.db.pages

    @property
    def scraping_jobs(self):
        return self.db.scraping_jobs

    @property
    def url_queue(self):
        return self.db.url_queue

    @property
    def site_structure(self):
        return self.db.site_structure 