# DocuFlow: Technical Overview

This document explains, in human terms, how **DocuFlow** scrapes and organizes all content from [vijayshree.netlify.app](https://vijayshree.netlify.app/) (my portfolio website), and why it’s designed the way it is. It’s meant for engineers, product managers, and anyone curious about the architecture and design choices.

[GitHub Repo: DocuFlow](https://github.com/vijayshreepathak/DocuFlow)

---

## 1. System Goals
- **Crawl and extract** every page (especially docs) from the website
- **Store each page** as a separate, structured document in MongoDB
- **Enable fast search, retrieval, and analytics**
- **Support incremental updates and deduplication**
- **Scale out** using distributed workers (Celery + Redis)
- **Be easy to deploy and maintain** (Docker)

---

## 2. High-Level Architecture

```mermaid
flowchart TD
    %% ========= Client =========
    subgraph Client
        U1["User / API Client"]
    end

    %% ========= API Layer =========
    subgraph "API Layer"
        A1["FastAPI REST API"]
    end

    %% ========= Scraper Cluster =========
    subgraph "Scraper Cluster"
        S1["Async Scraper<br/>(aiohttp + BeautifulSoup)"]
        W1["Celery Worker Pool"]
        B1["Celery Beat<br/>(Scheduler)"]
    end

    %% ========= Data Layer =========
    subgraph "Data Layer"
        M1["MongoDB<br/>(pages, jobs, structure)"]
        R1["Redis<br/>(Celery Broker / Cache)"]
    end

    %% ========= Monitoring =========
    subgraph Monitoring
        F1["Flower Dashboard"]
        L1["Centralised Logging"]
    end

    %% ---------- Primary user flow ----------
    U1 ==> |HTTP JSON requests| A1
    A1 ==> |CRUD pages / jobs| M1
    A1 -.-> |enqueue scrape task| R1

    %% ---------- Scraping & task processing ----------
    B1 --> |periodic enqueue| R1
    R1 --> |pop task| W1
    W1 --> |invoke scraper| S1
    S1 --> |read/write content| M1
    W1 --> |store results / status| M1

    %% ---------- Monitoring ----------
    F1 --- |stats & metrics| R1
    F1 --- |worker heartbeat| W1
    L1 --- A1
    L1 --- S1
    L1 --- W1
    L1 --- B1

    %% ---------- Notes ----------
    classDef faded fill:#ffffff,stroke:#bbb,color:#888;
    %% (optional) uncomment to fade internal arrows
    %% linkStyle default stroke-width:1,stroke:#888,fill:none;

```

**Explanation:**
- **User/API Client** interacts with the FastAPI REST API.
- **API Layer** handles requests, submits tasks, and reads/writes to MongoDB.
- **Scraper Cluster** (Scraper, Celery Workers, Beat) performs distributed crawling, processing, and scheduling.
- **Data Layer** (MongoDB, Redis) stores all content and manages distributed task queues.
- **Monitoring** (Flower, Logs) provides real-time and historical system insights.
- Arrows show the flow of data and tasks between components, reflecting DocuFlow's distributed, scalable, and production-ready design.

---

## 3. Data Flow (Step by Step)

1. **Start**: The system begins with one or more start URLs (e.g., the homepage or docs root)
2. **Crawling**: The scraper discovers all internal links, queues them, and fetches each page
3. **Processing**: Each page’s HTML is parsed and structured (headings, paragraphs, images, links, etc.)
4. **Deduplication**: Pages are hashed (MD5 of clean text) to avoid storing duplicates
5. **Storage**: Each page is saved as a document in MongoDB, with all content and metadata
6. **Incremental Updates**: If a page changes, only the new version is stored (with versioning)
7. **API Access**: Users can search, filter, and retrieve pages via the REST API
8. **Distributed Processing**: Celery workers allow many pages to be processed at once, scaling horizontally

---

## 4. MongoDB Schema Design (Why Page-wise?)

- **Each page = one document** in the `pages` collection
- This makes it easy to:
  - Retrieve a whole page (all content, metadata, links, images, etc.) in one query
  - Index and search across all pages
  - Update or deduplicate pages efficiently
- **Schema Example:**

```json
{
  "url": "https://vijayshree.netlify.app/docs/page1",
  "title": "Getting Started",
  "content": {
    "raw_html": "<html>...</html>",
    "clean_text": "Welcome to the docs...",
    "structured_data": {
      "headings": [ ... ],
      "paragraphs": [ ... ],
      "images": [ ... ],
      "links": [ ... ],
      ...
    },
    "content_hash": "md5hash",
    "word_count": 350,
    "reading_time": 2
  },
  "metadata": {
    "scraped_at": "2024-07-25T12:00:00Z",
    "last_updated": "2024-07-25T12:00:00Z",
    ...
  },
  "navigation": {
    "breadcrumb": ["Docs", "Getting Started"],
    "section": "docs",
    "subsection": "getting-started",
    ...
  },
  "seo": { ... },
  "status": "processed",
  ...
}
```

- **Indexes**: Unique on `url`, text index for search, etc.
- **Other collections**: `scraping_jobs`, `url_queue`, `site_structure` for job tracking, queueing, and site map.

---

## 5. Distributed Scraping & Processing

- **Celery + Redis**: The system can run many scraper/processor workers in parallel, so it can crawl large sites quickly
- **Queueing**: URLs to be scraped are queued in MongoDB and/or Redis
- **Deduplication**: URLs and content hashes are checked before scraping/storing
- **Incremental**: If a page is already up-to-date (same hash), it’s skipped

---

## 6. API & Search

- **FastAPI**: Exposes endpoints for search, retrieval, and analytics
- **Text Search**: Uses MongoDB’s text indexes for fast, full-text search
- **Filtering**: By section, quality, tags, etc.
- **Pagination**: For large result sets
- **Job Monitoring**: See scraping job status, errors, and progress

---

## 7. Extensibility & Customization

- **Add new fields** to the schema as needed (e.g., tags, categories, custom metadata)
- **Plug in NLP** for smarter keyword extraction or summarization
- **Add authentication** to the API for private deployments
- **Integrate with other databases** or search engines if needed

---

## 8. Troubleshooting & Tips

- **Docker Issues**: Ensure all required directories (`logs`, `data`) exist before building
- **MongoDB/Redis**: Make sure ports are not blocked and you have enough disk space
- **Scaling**: Increase the number of Celery workers for faster scraping
- **Monitoring**: Use Flower dashboard (`localhost:5555`) to monitor tasks
- **Logs**: Check the `logs/` directory for detailed logs

---

## 9. Why This Design?

- **Page-wise storage**: Makes retrieval, deduplication, and search simple and efficient
- **Distributed**: Handles large sites and scales with demand
- **API-first**: Easy integration with other tools, dashboards, or analytics
- **Dockerized**: Consistent, reproducible deployments

---

## 10. Diagrams

### System Flow

```mermaid
sequenceDiagram
    participant User
    participant API
    participant Scraper
    participant Celery
    participant MongoDB
    participant Redis
    User->>API: Search/Request
    API->>MongoDB: Query
    API-->>User: Results
    Scraper->>MongoDB: Store page
    Scraper->>Celery: Queue tasks
    Celery->>Scraper: Process URLs
    Scraper->>Redis: Use queue
```

### Data Model (Simplified)

```mermaid
classDiagram
    class Page {
      +string url
      +string title
      +Content content
      +Metadata metadata
      +Navigation navigation
      +SEO seo
      +string status
      +int version
      +float quality_score
      +Accessibility accessibility
    }
    class Content {
      +string raw_html
      +string clean_text
      +StructuredData structured_data
      +string content_hash
      +int word_count
      +int reading_time
    }
    class StructuredData {
      +list headings
      +list paragraphs
      +list code_blocks
      +list images
      +list links
      +list tables
      +list lists
    }
```

---

## 11. Summary

**DocuFlow** is designed to be robust, scalable, and easy to use for scraping and managing all content from a documentation-rich website like vijayshree.netlify.app. It’s suitable for personal portfolios, knowledge bases, or any site where page-wise, structured content is valuable.

For questions or contributions, see the main README or visit the [GitHub Repo: DocuFlow](https://github.com/vijayshreepathak/DocuFlow). 
