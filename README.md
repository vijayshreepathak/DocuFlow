# DocuFlow

A production-ready, distributed web scraping and data management system that crawls [vijayshree.netlify.app](https://vijayshree.netlify.app/) (my portfolio website), extracts all documentation and content page-wise, processes and structures the data, and stores it in MongoDB for efficient retrieval and search.

[![GitHub Repo](https://img.shields.io/badge/GitHub-DocuFlow-blue?logo=github)](https://github.com/vijayshreepathak/DocuFlow)

---

## 🚀 **Project Overview**

This system is designed to:
- **Crawl and scrape** all pages (especially docs) from vijayshree.netlify.app
- **Extract, clean, and structure** all content (text, images, links, metadata)
- **Store each page** as a document in MongoDB, with rich schema and indexing
- **Support incremental updates, deduplication, and distributed processing**
- **Expose a FastAPI REST API** for search, retrieval, and analytics
- **Run in Docker** for easy deployment and scaling

---

## 🏗️ **System Architecture**

```mermaid
flowchart TD
    subgraph User
        U1[User / API Client]
    end

    subgraph API Layer
        A1[FastAPI REST API]
    end

    subgraph Scraper Cluster
        S1[Scraper (Async, aiohttp, BeautifulSoup)]
        W1[Celery Worker(s)]
        B1[Celery Beat (Scheduler)]
    end

    subgraph Data Layer
        M1[MongoDB<br/>(pages, jobs, queue, structure)]
        R1[Redis<br/>(Celery Broker/Queue)]
    end

    subgraph Monitoring
        F1[Flower Dashboard]
        L1[Logs/Monitoring]
    end

    U1-->|HTTP Requests|A1
    A1-->|Task Submission|R1
    A1-->|Read/Write|M1
    S1-->|Scrape/Process|M1
    S1-->|Queue Tasks|R1
    W1-->|Process Tasks|S1
    W1-->|Write Results|M1
    B1-->|Schedule Tasks|R1
    F1-->|Monitor Celery|R1
    F1-->|Monitor Workers|W1
    L1-->|Logs|A1
    L1-->|Logs|S1
    L1-->|Logs|W1
    L1-->|Logs|B1

    %% Internal connections
    R1-->|Distributes Tasks|W1
    S1-->|Discovery/Queue|M1
    S1-->|Deduplication|M1
```

**Explanation:**
- **User/API Client** interacts with the FastAPI REST API.
- **API Layer** handles requests, submits tasks, and reads/writes to MongoDB.
- **Scraper Cluster** (Scraper, Celery Workers, Beat) performs distributed crawling, processing, and scheduling.
- **Data Layer** (MongoDB, Redis) stores all content and manages distributed task queues.
- **Monitoring** (Flower, Logs) provides real-time and historical system insights.
- Arrows show the flow of data and tasks between components, reflecting DocuFlow's distributed, scalable, and production-ready design.

---

## 🧩 **Main Components**

- **Scraper**: Crawls the site, extracts and structures content, manages deduplication and queueing.
- **Content Processor**: Cleans, parses, and structures HTML into rich data (headings, paragraphs, images, links, etc).
- **MongoDB**: Stores each page as a document, with full content, metadata, navigation, SEO, and search fields.
- **Celery + Redis**: Distributes scraping and post-processing tasks for scalability.
- **FastAPI**: Provides a REST API for search, retrieval, and analytics.
- **Docker**: All services run in containers for easy orchestration and scaling.

---

## 🗄️ **MongoDB Schema (Page-wise Storage)**

Each page is stored as a document in the `pages` collection. Example fields:

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

- **Each page is a separate document**
- **All content and metadata are stored for easy retrieval and search**
- **Indexes**: Unique on `url`, text index for search, etc.

---

## 🛠️ **Technology Stack**

- **Python 3.9+**
- **MongoDB 7.0+**
- **Scrapy, BeautifulSoup4, aiohttp**
- **FastAPI**
- **Celery + Redis**
- **Docker & Docker Compose**

---

## ⚙️ **Setup & Usage**

### 1. **Clone the Repository**
```sh
git clone https://github.com/vijayshreepathak/DocuFlow.git
cd DocuFlow
```

### 2. **Create Required Directories**
```sh
mkdir logs data
```

### 3. **Build and Run with Docker Compose**
```sh
docker-compose up --build
```
- This will start MongoDB, Redis, API, scraper, Celery workers, and monitoring (Flower)

### 4. **Access the API**
- Open [http://localhost:8000](http://localhost:8000) for the FastAPI docs and endpoints
- Flower dashboard: [http://localhost:5555](http://localhost:5555)

### 5. **Trigger a Scraping Job**
- The system will automatically start scraping from the configured start URLs (vijayshree.netlify.app)
- You can monitor progress via the API or Flower

---

## 📖 **API Endpoints (Examples)**

- `GET /search?q=python` — Full-text search across all pages
- `GET /pages/{page_id}` — Get detailed content for a specific page
- `GET /pages` — List pages with filters (section, quality, etc)
- `GET /sections` — Get site structure (sections, subsections)
- `GET /structure` — Get full site structure and stats
- `GET /statistics` — Get scraping and content statistics
- `GET /jobs` — List scraping jobs
- `GET /jobs/{job_id}` — Get job details

---

## 🧑‍💻 **Development & Customization**

- All source code is in `src/`
- Scraper logic: `src/scraper/spider.py`
- API logic: `src/api/main.py`, `src/api/schemas.py`
- Database models: `src/database/`
- Celery tasks: `src/workers/`
- Config, logging, monitoring: `src/utils/`

---

## 📝 **How It Works (Summary)**

1. **Crawls vijayshree.netlify.app** and discovers all pages (especially docs)
2. **Extracts and structures** all content (text, images, links, metadata)
3. **Stores each page** as a document in MongoDB, with full content and metadata
4. **Indexes and deduplicates** content for efficient search and updates
5. **Exposes a REST API** for search, retrieval, and analytics
6. **Runs distributed** with Celery and Docker for scalability

---

## 📦 **Production-Ready Features**
- Incremental updates and deduplication
- Distributed scraping and processing
- Full-text search and filtering
- Error handling and monitoring
- Dockerized for easy deployment

---

## 📚 **Further Reading**
- See `docs/` for detailed design, API reference, and architecture notes
- See `src/` for all implementation details

---

## © 2025 Vijayshree Vaibhav

This project scrapes and organizes data from [vijayshree.netlify.app](https://vijayshree.netlify.app/) (my portfolio website) for educational and portfolio demonstration purposes.

[GitHub Repo: DocuFlow](https://github.com/vijayshreepathak/DocuFlow) 
