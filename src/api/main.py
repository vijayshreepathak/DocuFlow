from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict
import asyncio
from contextlib import asynccontextmanager
from database.connection import DatabaseManager
from api.schemas import *
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_manager
    db_manager = DatabaseManager(
        os.getenv('MONGODB_URL', 'mongodb://mongodb:27017/vijayshreepathak_scraper?authSource=admin'),
        os.getenv('MONGODB_DB', 'vijayshreepathak_scraper')
    )
    await db_manager.connect()
    yield
    await db_manager.close()

app = FastAPI(
    title="VijayShree Pathak Website Scraper API",
    description="API for accessing scraped content from vijayshreepathak.netlify.app",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    return db_manager

@app.get("/", response_model=Dict)
async def root():
    return {
        "message": "VijayShree Pathak Website Scraper API",
        "version": "1.0.0",
        "status": "active",
        "endpoints": {
            "search": "/search",
            "pages": "/pages",
            "sections": "/sections",
            "structure": "/structure",
            "statistics": "/statistics",
            "jobs": "/jobs"
        }
    }

@app.get("/search", response_model=SearchResponse)
async def search_content(
    q: str = Query(..., description="Search query"),
    section: Optional[str] = Query(None, description="Filter by section"),
    subsection: Optional[str] = Query(None, description="Filter by subsection"),
    min_quality: Optional[int] = Query(None, description="Minimum quality score"),
    limit: int = Query(10, ge=1, le=100, description="Number of results"),
    skip: int = Query(0, ge=0, description="Number of results to skip"),
    db: DatabaseManager = Depends(get_db)
):
    try:
        filters = {}
        if section:
            filters['navigation.section'] = section
        if subsection:
            filters['navigation.subsection'] = subsection
        if min_quality:
            filters['quality_score'] = {'$gte': min_quality}
        results = await db.search_pages(q, filters, limit, skip)
        return SearchResponse(
            query=q,
            total_results=len(results),
            results=[PageSummary.from_db_doc(doc) for doc in results],
            filters=filters
        )
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail="Search failed")

@app.get("/pages/{page_id}", response_model=PageDetail)
async def get_page(
    page_id: str,
    db: DatabaseManager = Depends(get_db)
):
    try:
        from bson import ObjectId
        page = await db.db.pages.find_one({"_id": ObjectId(page_id)})
        if not page:
            raise HTTPException(status_code=404, detail="Page not found")
        return PageDetail.from_db_doc(page)
    except Exception as e:
        logger.error(f"Get page error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve page")

@app.get("/pages", response_model=List[PageSummary])
async def list_pages(
    section: Optional[str] = Query(None, description="Filter by section"),
    subsection: Optional[str] = Query(None, description="Filter by subsection"),
    min_quality: Optional[int] = Query(None, description="Minimum quality score"),
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db: DatabaseManager = Depends(get_db)
):
    try:
        query = {}
        if section:
            query['navigation.section'] = section
        if subsection:
            query['navigation.subsection'] = subsection
        if min_quality:
            query['quality_score'] = {'$gte': min_quality}
        cursor = db.db.pages.find(query).sort([
            ('quality_score', -1),
            ('metadata.last_updated', -1)
        ]).skip(skip).limit(limit)
        pages = await cursor.to_list(length=limit)
        return [PageSummary.from_db_doc(page) for page in pages]
    except Exception as e:
        logger.error(f"List pages error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list pages")

@app.get("/sections", response_model=List[SectionInfo])
async def get_sections(db: DatabaseManager = Depends(get_db)):
    try:
        structure = await db.get_site_structure()
        sections = {}
        for item in structure:
            section_name = item['_id']['section'] or 'root'
            subsection_name = item['_id']['subsection']
            if section_name not in sections:
                sections[section_name] = {
                    'name': section_name,
                    'total_pages': 0,
                    'avg_quality': 0,
                    'subsections': {}
                }
            sections[section_name]['total_pages'] += item['count']
            sections[section_name]['avg_quality'] += item['avg_quality'] * item['count']
            if subsection_name:
                sections[section_name]['subsections'][subsection_name] = {
                    'name': subsection_name,
                    'page_count': item['count'],
                    'avg_quality': item['avg_quality'],
                    'pages': item['pages']
                }
        for section in sections.values():
            if section['total_pages'] > 0:
                section['avg_quality'] /= section['total_pages']
        return [
            SectionInfo(
                name=section['name'],
                page_count=section['total_pages'],
                avg_quality_score=section['avg_quality'],
                subsections=[
                    SubsectionInfo(
                        name=sub['name'],
                        page_count=sub['page_count'],
                        avg_quality_score=sub['avg_quality']
                    )
                    for sub in section['subsections'].values()
                ]
            )
            for section in sections.values()
        ]
    except Exception as e:
        logger.error(f"Get sections error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get sections")

@app.get("/structure", response_model=SiteStructure)
async def get_site_structure(db: DatabaseManager = Depends(get_db)):
    try:
        structure = await db.get_site_structure()
        stats = await db.get_content_statistics()
        return SiteStructure(
            total_pages=stats.get('total_pages', 0),
            total_words=stats.get('total_words', 0),
            avg_quality_score=stats.get('avg_quality_score', 0),
            sections=[
                SectionStructure(
                    section=item['_id']['section'] or 'root',
                    subsection=item['_id']['subsection'],
                    page_count=item['count'],
                    avg_quality=item['avg_quality'],
                    pages=[
                        PageInfo(
                            title=page['title'],
                            url=page['url'],
                            quality_score=page['quality_score']
                        )
                        for page in item['pages']
                    ]
                )
                for item in structure
            ]
        )
    except Exception as e:
        logger.error(f"Get structure error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get site structure")

@app.get("/statistics", response_model=StatisticsResponse)
async def get_statistics(db: DatabaseManager = Depends(get_db)):
    try:
        content_stats = await db.get_content_statistics()
        latest_job = await db.db.scraping_jobs.find_one(
            sort=[('start_time', -1)]
        )
        job_stats = {}
        if latest_job:
            job_stats = {
                'job_name': latest_job['job_name'],
                'status': latest_job['status'],
                'start_time': latest_job['start_time'],
                'end_time': latest_job.get('end_time'),
                'statistics': latest_job['statistics'],
                'progress': latest_job.get('progress', {})
            }
        return StatisticsResponse(
            content_statistics=content_stats,
            latest_job=job_stats
        )
    except Exception as e:
        logger.error(f"Get statistics error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")

@app.get("/jobs", response_model=List[JobSummary])
async def list_jobs(
    limit: int = Query(10, ge=1, le=50),
    db: DatabaseManager = Depends(get_db)
):
    try:
        cursor = db.db.scraping_jobs.find().sort([
            ('start_time', -1)
        ]).limit(limit)
        jobs = await cursor.to_list(length=limit)
        return [JobSummary.from_db_doc(job) for job in jobs]
    except Exception as e:
        logger.error(f"List jobs error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list jobs")

@app.get("/jobs/{job_id}", response_model=JobDetail)
async def get_job(
    job_id: str,
    db: DatabaseManager = Depends(get_db)
):
    try:
        from bson import ObjectId
        job = await db.db.scraping_jobs.find_one({"_id": ObjectId(job_id)})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobDetail.from_db_doc(job)
    except Exception as e:
        logger.error(f"Get job error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve job")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 