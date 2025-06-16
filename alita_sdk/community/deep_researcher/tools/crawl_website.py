from typing import List, Set, Union
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import aiohttp
from .web_search import scrape_urls, ssl_context, ScrapeResult, WebpageSnippet
from agents import function_tool


@function_tool
async def crawl_website(starting_url: str) -> Union[List[ScrapeResult], str]:
    """Crawls the pages of a website starting with the starting_url and then descending into the pages linked from there.
    Prioritizes links found in headers/navigation, then body links, then subsequent pages.
    
    Args:
        starting_url: Starting URL to scrape
        
    Returns:
        List of ScrapeResult objects which have the following fields:
            - url: The URL of the web page
            - title: The title of the web page
            - description: The description of the web page
            - text: The text content of the web page
    """
    if not starting_url:
        return "Empty URL provided"

    # Ensure URL has a protocol
    if not starting_url.startswith(('http://', 'https://')):
        starting_url = 'http://' + starting_url

    max_pages = 10
    base_domain = urlparse(starting_url).netloc
    
    async def extract_links(html: str, current_url: str) -> tuple[List[str], List[str]]:
        """Extract prioritized links from HTML content"""
        soup = BeautifulSoup(html, 'html.parser')
        nav_links = set()
        body_links = set()
        
        # Find navigation/header links
        for nav_element in soup.find_all(['nav', 'header']):
            for a in nav_element.find_all('a', href=True):
                link = urljoin(current_url, a['href'])
                if urlparse(link).netloc == base_domain:
                    nav_links.add(link)
        
        # Find remaining body links
        for a in soup.find_all('a', href=True):
            link = urljoin(current_url, a['href'])
            if urlparse(link).netloc == base_domain and link not in nav_links:
                body_links.add(link)
                
        return list(nav_links), list(body_links)

    async def fetch_page(url: str) -> str:
        """Fetch HTML content from a URL"""
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        return await response.text()
            except Exception as e:
                print(f"Error fetching {url}: {str(e)}")
                return "Error fetching page"

    # Initialize with starting URL
    queue: List[str] = [starting_url]
    next_level_queue: List[str] = []
    all_pages_to_scrape: Set[str] = set([starting_url])
    
    # Breadth-first crawl
    while queue and len(all_pages_to_scrape) < max_pages:
        current_url = queue.pop(0)
        
        # Fetch and process the page
        html_content = await fetch_page(current_url)
        if html_content:
            nav_links, body_links = await extract_links(html_content, current_url)
            
            # Add unvisited nav links to current queue (higher priority)
            remaining_slots = max_pages - len(all_pages_to_scrape)
            for link in nav_links:
                link = link.rstrip('/')
                if link not in all_pages_to_scrape and remaining_slots > 0:
                    queue.append(link)
                    all_pages_to_scrape.add(link)
                    remaining_slots -= 1
            
            # Add unvisited body links to next level queue (lower priority)
            for link in body_links:
                link = link.rstrip('/')
                if link not in all_pages_to_scrape and remaining_slots > 0:
                    next_level_queue.append(link)
                    all_pages_to_scrape.add(link)
                    remaining_slots -= 1
        
        # If current queue is empty, add next level links
        if not queue:
            queue = next_level_queue
            next_level_queue = []
    
    # Convert set to list for final processing
    pages_to_scrape = list(all_pages_to_scrape)[:max_pages]
    pages_to_scrape = [WebpageSnippet(url=page, title="", description="") for page in pages_to_scrape]
    
    # Use scrape_urls to get the content for all discovered pages
    result = await scrape_urls(pages_to_scrape)
    return result