from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class PageType(str, Enum):
    home = "home"
    article = "article"
    blog = "blog"
    documentation = "documentation"
    about = "about"
    contact = "contact"

class LinkType(str, Enum):
    internal = "internal"
    external = "external"
    anchor = "anchor"

class JobStatus(str, Enum):
    running = "running"
    completed = "completed"
    failed = "failed"
    paused = "paused"
    cancelled = "cancelled"

class Heading(BaseModel):
    level: str
    text: str
    id: Optional[str] = ""
    anchor: Optional[str] = ""

class CodeBlock(BaseModel):
    language: Optional[str] = ""
    content: str
    file_name: Optional[str] = ""

class Image(BaseModel):
    src: HttpUrl
    alt: str
    title: Optional[str] = ""
    caption: Optional[str] = ""
    local_path: Optional[str] = ""

class Link(BaseModel):
    href: str
    text: str
    title: Optional[str] = ""
    type: LinkType
    status: Optional[str] = "pending"

class Table(BaseModel):
    headers: List[str]
    rows: List[List[str]]
    caption: Optional[str] = ""

class ListItem(BaseModel):
    type: str  # ordered, unordered
    items: List[str]

class StructuredContent(BaseModel):
    headings: List[Heading]
    paragraphs: List[str]
    code_blocks: List[CodeBlock]
    images: List[Image]
    links: List[Link]
    tables: List[Table]
    lists: List[ListItem]

class Content(BaseModel):
    raw_html: Optional[str] = ""
    clean_text: str
    structured_data: StructuredContent
    content_hash: str
    word_count: int
    reading_time: int

class Metadata(BaseModel):
    scraped_at: datetime
    last_updated: datetime
    last_modified: Optional[datetime] = None
    etag: Optional[str] = ""
    scraping_job_id: str
    page_depth: Optional[int] = 0
    parent_url: Optional[str] = ""
    response_time: float
    status_code: int
    content_length: int
    language: str = "en"
    charset: str = "utf-8"

class Navigation(BaseModel):
    breadcrumb: List[str]
    next_page: Optional[str] = ""
    prev_page: Optional[str] = ""
    section: Optional[str] = ""
    subsection: Optional[str] = ""
    page_type: PageType = PageType.article
    menu_position: int = 0

class SEO(BaseModel):
    meta_description: Optional[str] = ""
    meta_keywords: List[str] = []
    og_title: Optional[str] = ""
    og_description: Optional[str] = ""
    og_image: Optional[str] = ""
    canonical_url: Optional[str] = ""

class SearchFields(BaseModel):
    searchable_text: str
    keywords: List[str]
    tags: List[str]
    categories: List[str]

class Accessibility(BaseModel):
    has_alt_text: bool
    has_headings: bool
    color_contrast: str = "unknown"
    readability_score: float

class PageSummary(BaseModel):
    id: str = Field(alias="_id")
    url: HttpUrl
    title: str
    section: Optional[str] = ""
    subsection: Optional[str] = ""
    word_count: int
    reading_time: int
    quality_score: float
    scraped_at: datetime
    @classmethod
    def from_db_doc(cls, doc: Dict) -> "PageSummary":
        return cls(
            _id=str(doc["_id"]),
            url=doc["url"],
            title=doc["title"],
            section=doc["navigation"]["section"],
            subsection=doc["navigation"]["subsection"],
            word_count=doc["content"]["word_count"],
            reading_time=doc["content"]["reading_time"],
            quality_score=doc["quality_score"],
            scraped_at=doc["metadata"]["scraped_at"]
        )

class PageDetail(BaseModel):
    id: str = Field(alias="_id")
    url: HttpUrl
    title: str
    content: Content
    metadata: Metadata
    navigation: Navigation
    seo: SEO
    search_fields: SearchFields
    status: str
    version: int
    quality_score: float
    accessibility: Accessibility
    @classmethod
    def from_db_doc(cls, doc: Dict) -> "PageDetail":
        return cls(
            _id=str(doc["_id"]),
            **doc
        )

class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[PageSummary]
    filters: Dict[str, Any]

class SubsectionInfo(BaseModel):
    name: str
    page_count: int
    avg_quality_score: float

class SectionInfo(BaseModel):
    name: str
    page_count: int
    avg_quality_score: float
    subsections: List[SubsectionInfo]

class PageInfo(BaseModel):
    title: str
    url: HttpUrl
    quality_score: float

class SectionStructure(BaseModel):
    section: str
    subsection: Optional[str]
    page_count: int
    avg_quality: float
    pages: List[PageInfo]

class SiteStructure(BaseModel):
    total_pages: int
    total_words: int
    avg_quality_score: float
    sections: List[SectionStructure]

class JobStatistics(BaseModel):
    total_urls_discovered: int
    total_urls_processed: int
    successfully_scraped: int
    failed_urls: int
    duplicate_urls: int
    total_size_mb: float

class JobProgress(BaseModel):
    urls_in_queue: int
    urls_being_processed: int
    percentage_complete: float

class JobSummary(BaseModel):
    id: str = Field(alias="_id")
    job_name: str
    status: JobStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    statistics: JobStatistics
    @classmethod
    def from_db_doc(cls, doc: Dict) -> "JobSummary":
        return cls(
            _id=str(doc["_id"]),
            job_name=doc["job_name"],
            status=doc["status"],
            start_time=doc["start_time"],
            end_time=doc.get("end_time"),
            statistics=JobStatistics(**doc["statistics"])
        )

class JobError(BaseModel):
    url: str
    error_type: str
    error_message: str
    status_code: int
    timestamp: datetime
    retry_count: int

class JobDetail(BaseModel):
    id: str = Field(alias="_id")
    job_name: str
    job_type: str
    status: JobStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    configuration: Dict[str, Any]
    statistics: JobStatistics
    progress: JobProgress
    errors: List[JobError]
    @classmethod
    def from_db_doc(cls, doc: Dict) -> "JobDetail":
        return cls(
            _id=str(doc["_id"]),
            job_name=doc["job_name"],
            job_type=doc["job_type"],
            status=doc["status"],
            start_time=doc["start_time"],
            end_time=doc.get("end_time"),
            configuration=doc["configuration"],
            statistics=JobStatistics(**doc["statistics"]),
            progress=JobProgress(**doc.get("progress", {})),
            errors=[JobError(**error) for error in doc.get("errors", [])]
        )

class StatisticsResponse(BaseModel):
    content_statistics: Dict[str, Any]
    latest_job: Dict[str, Any] 