import scrapy
import requests
from scrapy.http import Request
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import hashlib
import time
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional, Generator
import re
from dataclasses import dataclass
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
from urllib.robotparser import RobotFileParser

@dataclass
class ScrapingConfig:
    start_urls: List[str]
    allowed_domains: List[str]
    max_depth: int = 10
    delay_between_requests: float = 1.0
    concurrent_requests: int = 16
    max_pages: int = 10000
    timeout: int = 30
    retry_attempts: int = 3
    respect_robots_txt: bool = True
    download_images: bool = False
    user_agent: str = "VijayPathaBot 1.0 (Educational Web Scraper)"
    excluded_patterns: List[str] = None

class VijayPathakScraper:
    def __init__(self, config: ScrapingConfig, db_manager):
        self.config = config
        self.db = db_manager
        self.session = None
        self.robots_parser = None
        self.discovered_urls = set()
        self.processed_urls = set()
        self.failed_urls = set()
        self.current_job_id = None
        self.logger = logging.getLogger(__name__)
        if self.config.respect_robots_txt:
            self.init_robots_parser()

    def init_robots_parser(self):
        try:
            robots_url = f"{self.config.start_urls[0].rstrip('/')}/robots.txt"
            self.robots_parser = RobotFileParser()
            self.robots_parser.set_url(robots_url)
            self.robots_parser.read()
        except Exception as e:
            self.logger.warning(f"Could not parse robots.txt: {e}")

    async def start_scraping_job(self) -> str:
        job_config = {
            'start_urls': self.config.start_urls,
            'allowed_domains': self.config.allowed_domains,
            'max_depth': self.config.max_depth,
            'delay_between_requests': self.config.delay_between_requests,
            'concurrent_requests': self.config.concurrent_requests,
            'user_agent': self.config.user_agent,
            'respect_robots_txt': self.config.respect_robots_txt,
            'download_images': self.config.download_images,
            'timeout': self.config.timeout,
            'retry_attempts': self.config.retry_attempts
        }
        job_doc = {
            'job_name': f"vijayshreepathak_scrape_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'job_type': 'full_crawl',
            'start_time': datetime.utcnow(),
            'status': 'running',
            'configuration': job_config,
            'statistics': {
                'total_urls_discovered': 0,
                'total_urls_processed': 0,
                'successfully_scraped': 0,
                'failed_urls': 0,
                'duplicate_urls': 0,
                'total_size_mb': 0.0
            },
            'progress': {
                'current_depth': 0,
                'urls_in_queue': 0,
                'urls_being_processed': 0,
                'percentage_complete': 0.0
            },
            'errors': [],
            'notifications': []
        }
        self.current_job_id = await self.db.create_scraping_job(job_doc)
        for url in self.config.start_urls:
            await self.add_url_to_queue(url, depth=0, priority=1)
        return self.current_job_id

    async def add_url_to_queue(self, url: str, depth: int = 0, priority: int = 2, parent_url: str = None, discovery_method: str = "manual"):
        normalized_url = self.normalize_url(url)
        if normalized_url in self.discovered_urls:
            await self.db.increment_job_stat(self.current_job_id, 'duplicate_urls')
            return False
        if self.robots_parser and not self.robots_parser.can_fetch(self.config.user_agent, url):
            self.logger.info(f"URL blocked by robots.txt: {url}")
            return False
        if self.config.excluded_patterns:
            for pattern in self.config.excluded_patterns:
                if re.search(pattern, url):
                    self.logger.info(f"URL excluded by pattern {pattern}: {url}")
                    return False
        self.discovered_urls.add(normalized_url)
        queue_doc = {
            'url': url,
            'normalized_url': normalized_url,
            'status': 'pending',
            'priority': priority,
            'discovered_at': datetime.utcnow(),
            'first_seen_on': parent_url,
            'attempts': 0,
            'job_id': self.current_job_id,
            'depth': depth,
            'parent_url': parent_url,
            'discovery_method': discovery_method,
            'estimated_processing_time': 0
        }
        await self.db.add_to_url_queue(queue_doc)
        await self.db.increment_job_stat(self.current_job_id, 'total_urls_discovered')
        return True

    def normalize_url(self, url: str) -> str:
        parsed = urlparse(url.lower().strip())
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            query_parts = sorted(parsed.query.split('&'))
            normalized += f"?{'&'.join(query_parts)}"
        if normalized.endswith('/') and normalized.count('/') > 3:
            normalized = normalized.rstrip('/')
        return normalized

    async def process_queue(self):
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            headers={'User-Agent': self.config.user_agent}
        ) as session:
            self.session = session
            while True:
                urls_to_process = await self.db.get_pending_urls(
                    self.current_job_id, 
                    limit=self.config.concurrent_requests
                )
                if not urls_to_process:
                    stats = await self.db.get_job_statistics(self.current_job_id)
                    if stats['progress']['urls_in_queue'] == 0:
                        break
                    await asyncio.sleep(5)
                    continue
                tasks = []
                for url_doc in urls_to_process:
                    task = asyncio.create_task(
                        self.process_single_url(url_doc)
                    )
                    tasks.append(task)
                await asyncio.gather(*tasks, return_exceptions=True)
                if self.config.delay_between_requests > 0:
                    await asyncio.sleep(self.config.delay_between_requests)
        await self.db.complete_scraping_job(self.current_job_id)

    async def process_single_url(self, url_doc: Dict):
        url = url_doc['url']
        url_id = url_doc['_id']
        try:
            await self.db.update_url_status(url_id, 'processing')
            start_time = time.time()
            async with self.session.get(url) as response:
                if response.status >= 400:
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status
                    )
                content = await response.read()
                content_type = response.headers.get('content-type', '').lower()
                if 'text/html' not in content_type:
                    await self.db.update_url_status(url_id, 'skipped')
                    return
                processing_time = time.time() - start_time
                page_data = await self.extract_page_content(
                    url, content, response.headers, processing_time
                )
                await self.db.save_page_data(page_data)
                new_urls = self.discover_urls_from_content(content, url)
                if url_doc['depth'] < self.config.max_depth:
                    for new_url in new_urls:
                        await self.add_url_to_queue(new_url, depth=url_doc['depth']+1, parent_url=url)
            await self.db.update_url_status(url_id, 'completed')
            await self.db.increment_job_stat(self.current_job_id, 'successfully_scraped')
        except Exception as e:
            await self.handle_url_error(url_doc, str(e))

    async def extract_page_content(self, url: str, content: bytes, headers: Dict, processing_time: float) -> Dict:
        soup = BeautifulSoup(content, 'html.parser')
        for element in soup(['script', 'style', 'nav', 'footer', 'aside', 'advertisement']):
            element.decompose()
        title = soup.title.string.strip() if soup.title else ''
        structured_data = await self.extract_structured_content(soup, url)
        clean_text = soup.get_text(strip=True, separator=' ')
        word_count = len(clean_text.split())
        reading_time = max(1, word_count // 200)
        content_hash = hashlib.md5(clean_text.encode()).hexdigest()
        navigation = self.extract_navigation_info(soup, url)
        seo_data = self.extract_seo_metadata(soup)
        quality_score = self.calculate_quality_score(soup, structured_data)
        accessibility = self.check_accessibility(soup)
        page_data = {
            'url': url,
            'title': title,
            'content': {
                'raw_html': str(soup),
                'clean_text': clean_text,
                'structured_data': structured_data,
                'content_hash': content_hash,
                'word_count': word_count,
                'reading_time': reading_time
            },
            'metadata': {
                'scraped_at': datetime.utcnow(),
                'last_updated': datetime.utcnow(),
                'last_modified': headers.get('last-modified'),
                'etag': headers.get('etag'),
                'scraping_job_id': self.current_job_id,
                'response_time': processing_time,
                'status_code': 200,
                'content_length': len(content),
                'language': soup.get('lang', 'en'),
                'charset': 'utf-8'
            },
            'navigation': navigation,
            'seo': seo_data,
            'search_fields': {
                'searchable_text': f"{title} {clean_text}",
                'keywords': self.extract_keywords(clean_text),
                'tags': [],
                'categories': []
            },
            'status': 'processed',
            'version': 1,
            'quality_score': quality_score,
            'accessibility': accessibility
        }
        return page_data

    async def extract_structured_content(self, soup: BeautifulSoup, base_url: str) -> Dict:
        structured = {
            'headings': [],
            'paragraphs': [],
            'code_blocks': [],
            'images': [],
            'links': [],
            'tables': [],
            'lists': []
        }
        for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            structured['headings'].append({
                'level': heading.name,
                'text': heading.get_text(strip=True),
                'id': heading.get('id', ''),
                'anchor': f"#{heading.get('id', '')}" if heading.get('id') else ''
            })
        for para in soup.find_all('p'):
            text = para.get_text(strip=True)
            if text and len(text) > 10:
                structured['paragraphs'].append(text)
        for code_element in soup.find_all(['code', 'pre']):
            language = ''
            classes = code_element.get('class', [])
            for cls in classes:
                if cls.startswith('language-') or cls.startswith('lang-'):
                    language = cls.split('-', 1)[-1]
                    break
            structured['code_blocks'].append({
                'language': language,
                'content': code_element.get_text(),
                'file_name': code_element.get('data-filename', '')
            })
        for img in soup.find_all('img'):
            src = img.get('src')
            if src:
                if src.startswith('/'):
                    src = urljoin(base_url, src)
                structured['images'].append({
                    'src': src,
                    'alt': img.get('alt', ''),
                    'title': img.get('title', ''),
                    'caption': self.get_image_caption(img),
                    'local_path': ''
                })
        for link in soup.find_all('a', href=True):
            href = urljoin(base_url, link['href'])
            link_text = link.get_text(strip=True)
            if link_text:
                parsed_base = urlparse(base_url)
                parsed_href = urlparse(href)
                link_type = 'internal' if parsed_href.netloc == parsed_base.netloc else 'external'
                if href.startswith('#'):
                    link_type = 'anchor'
                structured['links'].append({
                    'href': href,
                    'text': link_text,
                    'title': link.get('title', ''),
                    'type': link_type,
                    'status': 'pending'
                })
        for table in soup.find_all('table'):
            table_data = self.extract_table_data(table)
            if table_data:
                structured['tables'].append(table_data)
        for list_element in soup.find_all(['ul', 'ol']):
            list_items = [li.get_text(strip=True) for li in list_element.find_all('li')]
            if list_items:
                structured['lists'].append({
                    'type': 'ordered' if list_element.name == 'ol' else 'unordered',
                    'items': list_items
                })
        return structured

    def get_image_caption(self, img_element) -> str:
        figure = img_element.find_parent('figure')
        if figure:
            figcaption = figure.find('figcaption')
            if figcaption:
                return figcaption.get_text(strip=True)
        next_sibling = img_element.find_next_sibling(['p', 'div', 'span'])
        if next_sibling and 'caption' in next_sibling.get('class', []):
            return next_sibling.get_text(strip=True)
        return ''

    def extract_table_data(self, table) -> Optional[Dict]:
        rows = table.find_all('tr')
        if not rows:
            return None
        headers = []
        header_row = table.find('thead')
        if header_row:
            header_cells = header_row.find_all(['th', 'td'])
            headers = [cell.get_text(strip=True) for cell in header_cells]
        elif rows:
            first_row_cells = rows[0].find_all(['th', 'td'])
            if all(cell.name == 'th' for cell in first_row_cells):
                headers = [cell.get_text(strip=True) for cell in first_row_cells]
                rows = rows[1:]
        data_rows = []
        for row in rows:
            cells = row.find_all(['td', 'th'])
            row_data = [cell.get_text(strip=True) for cell in cells]
            if row_data:
                data_rows.append(row_data)
        if not data_rows:
            return None
        caption = ''
        caption_element = table.find('caption')
        if caption_element:
            caption = caption_element.get_text(strip=True)
        return {
            'headers': headers,
            'rows': data_rows,
            'caption': caption
        }

    def extract_navigation_info(self, soup: BeautifulSoup, url: str) -> Dict:
        navigation = {
            'breadcrumb': [],
            'next_page': '',
            'prev_page': '',
            'section': '',
            'subsection': '',
            'page_type': 'article',
            'menu_position': 0
        }
        breadcrumb_selectors = [
            '.breadcrumb', '.breadcrumbs', '[aria-label="breadcrumb"]',
            '.nav-breadcrumb', '#breadcrumb'
        ]
        for selector in breadcrumb_selectors:
            breadcrumb_element = soup.select_one(selector)
            if breadcrumb_element:
                links = breadcrumb_element.find_all(['a', 'span'])
                navigation['breadcrumb'] = [
                    link.get_text(strip=True) for link in links
                    if link.get_text(strip=True)
                ]
                break
        next_link = soup.find('a', text=re.compile(r'next|continue|forward', re.I))
        if next_link and next_link.get('href'):
            navigation['next_page'] = urljoin(url, next_link['href'])
        prev_link = soup.find('a', text=re.compile(r'previous|back|prev', re.I))
        if prev_link and prev_link.get('href'):
            navigation['prev_page'] = urljoin(url, prev_link['href'])
        parsed_url = urlparse(url)
        path_parts = [part for part in parsed_url.path.split('/') if part]
        if not path_parts:
            navigation['page_type'] = 'home'
        elif 'blog' in path_parts:
            navigation['page_type'] = 'blog'
            navigation['section'] = 'blog'
        elif 'docs' in path_parts or 'documentation' in path_parts:
            navigation['page_type'] = 'documentation'
            navigation['section'] = 'docs'
        elif 'about' in path_parts:
            navigation['page_type'] = 'about'
            navigation['section'] = 'about'
        elif 'contact' in path_parts:
            navigation['page_type'] = 'contact'
            navigation['section'] = 'contact'
        if len(path_parts) >= 1:
            navigation['section'] = path_parts[0]
        if len(path_parts) >= 2:
            navigation['subsection'] = path_parts[1]
        return navigation

    def extract_seo_metadata(self, soup: BeautifulSoup) -> Dict:
        seo = {
            'meta_description': '',
            'meta_keywords': [],
            'og_title': '',
            'og_description': '',
            'og_image': '',
            'canonical_url': ''
        }
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            seo['meta_description'] = meta_desc.get('content', '')
        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        if meta_keywords:
            keywords = meta_keywords.get('content', '')
            seo['meta_keywords'] = [k.strip() for k in keywords.split(',')]
        og_title = soup.find('meta', attrs={'property': 'og:title'})
        if og_title:
            seo['og_title'] = og_title.get('content', '')
        og_desc = soup.find('meta', attrs={'property': 'og:description'})
        if og_desc:
            seo['og_description'] = og_desc.get('content', '')
        og_image = soup.find('meta', attrs={'property': 'og:image'})
        if og_image:
            seo['og_image'] = og_image.get('content', '')
        canonical = soup.find('link', attrs={'rel': 'canonical'})
        if canonical:
            seo['canonical_url'] = canonical.get('href', '')
        return seo

    def extract_keywords(self, text: str, max_keywords: int = 20) -> List[str]:
        import re
        from collections import Counter
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'about', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'up', 'down', 'out', 'off',
            'over', 'under', 'again', 'further', 'then', 'once', 'is', 'are',
            'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do',
            'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
            'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he',
            'she', 'it', 'we', 'they', 'them', 'their', 'what', 'which', 'who',
            'when', 'where', 'why', 'how'
        }
        words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
        filtered_words = [word for word in words if word not in stop_words]
        word_freq = Counter(filtered_words)
        return [word for word, count in word_freq.most_common(max_keywords)]

    def calculate_quality_score(self, soup: BeautifulSoup, structured_data: Dict) -> float:
        score = 0
        if structured_data['headings']:
            score += 20
        if len(structured_data['paragraphs']) >= 3:
            score += 15
        if structured_data['images']:
            score += 10
            images_with_alt = sum(1 for img in structured_data['images'] if img['alt'])
            score += min(10, images_with_alt * 2)
        if structured_data['links']:
            score += 10
        total_text = ' '.join(structured_data['paragraphs'])
        word_count = len(total_text.split())
        if word_count >= 300:
            score += 15
        elif word_count >= 100:
            score += 10
        if soup.find('main') or soup.find('[role="main"]'):
            score += 5
        if soup.find('nav') or soup.find('[role="navigation"]'):
            score += 5
        if soup.find('meta', attrs={'name': 'description'}):
            score += 5
        if soup.title:
            score += 5
        return min(100, score)

    def check_accessibility(self, soup: BeautifulSoup) -> Dict:
        accessibility = {
            'has_alt_text': True,
            'has_headings': True,
            'color_contrast': 'unknown',
            'readability_score': 0
        }
        images = soup.find_all('img')
        if images:
            images_without_alt = [img for img in images if not img.get('alt')]
            accessibility['has_alt_text'] = len(images_without_alt) == 0
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        accessibility['has_headings'] = len(headings) > 0
        text = soup.get_text()
        if text:
            words = text.split()
            sentences = text.split('.')
            if len(sentences) > 0 and len(words) > 0:
                avg_words_per_sentence = len(words) / len(sentences)
                accessibility['readability_score'] = max(0, 100 - avg_words_per_sentence * 2)
        return accessibility

    def discover_urls_from_content(self, content: bytes, base_url: str) -> List[str]:
        soup = BeautifulSoup(content, 'html.parser')
        discovered_urls = set()
        for link in soup.find_all('a', href=True):
            url = urljoin(base_url, link['href'])
            parsed = urlparse(url)
            if parsed.netloc in self.config.allowed_domains:
                if not any(ext in parsed.path.lower() for ext in ['.pdf', '.jpg', '.png', '.gif', '.zip', '.doc']):
                    discovered_urls.add(url)
        sitemap_links = soup.find_all('a', href=re.compile(r'sitemap', re.I))
        for link in sitemap_links:
            url = urljoin(base_url, link['href'])
            if urlparse(url).netloc in self.config.allowed_domains:
                discovered_urls.add(url)
        return list(discovered_urls)

    async def handle_url_error(self, url_doc: Dict, error_message: str):
        url_id = url_doc['_id']
        attempts = url_doc.get('attempts', 0) + 1
        error_doc = {
            'url': url_doc['url'],
            'error_type': 'processing_error',
            'error_message': error_message,
            'status_code': getattr(error_message, 'status', 0),
            'timestamp': datetime.utcnow(),
            'retry_count': attempts
        }
        await self.db.log_scraping_error(self.current_job_id, error_doc)
        if attempts < self.config.retry_attempts:
            next_retry = datetime.utcnow() + timedelta(seconds=10 * attempts)
            await self.db.schedule_url_retry(url_id, next_retry, attempts)
        else:
            await self.db.update_url_status(url_id, 'failed')
            await self.db.increment_job_stat(self.current_job_id, 'failed_urls') 