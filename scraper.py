# scraper.py
# Async scraper — routes HTML requests through the Cloudflare Worker proxy.
# Sites with a dedicated API scraper (e.g. Aritzia via Algolia) bypass
# the HTML pipeline entirely.

import asyncio
import logging
import urllib.parse

import aiohttp
from bs4 import BeautifulSoup

from config import PROXY_BASE, PLAYWRIGHT_TIMEOUT_MS, PLAYWRIGHT_WAIT_SELECTOR
from product_extractor import (
    extract_product_links, extract_product,
    extract_products_from_listing, is_direct_extract,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Proxy URL builder
# ---------------------------------------------------------------------------

def proxied(target_url: str) -> str:
    encoded = urllib.parse.quote(target_url, safe="")
    return f"{PROXY_BASE}?url={encoded}"


# ---------------------------------------------------------------------------
# Plain HTTP fetch (aiohttp, proxy-routed)
# ---------------------------------------------------------------------------

async def fetch_html(session: aiohttp.ClientSession, url: str, delay: float = 1.0) -> str | None:
    await asyncio.sleep(delay)
    proxy_url = proxied(url)
    try:
        async with session.get(proxy_url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status != 200:
                logger.warning(f"HTTP {resp.status} for {url}")
                return None
            return await resp.text()
    except Exception as e:
        logger.error(f"Fetch error for {url}: {e}")
        return None


# ---------------------------------------------------------------------------
# Playwright fetch (JS-rendered sites, proxy-routed)
# ---------------------------------------------------------------------------

async def fetch_html_js(url: str, delay: float = 2.0) -> str | None:
    await asyncio.sleep(delay)
    proxy_url = proxied(url)
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                )
            )
            page = await context.new_page()
            await page.goto(proxy_url, timeout=PLAYWRIGHT_TIMEOUT_MS, wait_until="domcontentloaded")
            await page.wait_for_selector(PLAYWRIGHT_WAIT_SELECTOR, timeout=PLAYWRIGHT_TIMEOUT_MS)
            html = await page.content()
            await browser.close()
            return html
    except Exception as e:
        logger.error(f"Playwright error for {url}: {e}")
        return None


# ---------------------------------------------------------------------------
# Core HTML scrape logic for one site
# ---------------------------------------------------------------------------

async def scrape_site(site_key: str, site_config: dict) -> list[dict]:
    requires_js  = site_config["requires_js"]
    delay        = site_config["request_delay"]
    listing_urls = site_config["listing_urls"]

    products: list[dict]  = []
    seen_urls: set[str]   = set()

    async with aiohttp.ClientSession() as session:

        if is_direct_extract(site_key):
            # All product data lives on the listing page itself (e.g. Wayward/Squarespace)
            for listing_url in listing_urls:
                logger.info(f"[{site_key}] Listing (direct): {listing_url}")
                html = await fetch_html(session, listing_url, delay)
                if not html:
                    continue
                soup  = BeautifulSoup(html, "lxml")
                found = extract_products_from_listing(site_key, soup, listing_url)
                logger.info(f"[{site_key}] Extracted {len(found)} products from {listing_url}")
                for p in found:
                    if p["product_url"] not in seen_urls:
                        seen_urls.add(p["product_url"])
                        products.append(p)

        else:
            # Phase 1: collect product URLs from listing pages
            product_urls: list[str] = []
            for listing_url in listing_urls:
                logger.info(f"[{site_key}] Listing: {listing_url}")
                html = await (fetch_html_js(listing_url, delay) if requires_js
                              else fetch_html(session, listing_url, delay))
                if not html:
                    continue
                soup  = BeautifulSoup(html, "lxml")
                found = extract_product_links(site_key, soup, listing_url)
                logger.info(f"[{site_key}] Found {len(found)} product links on {listing_url}")
                for url in found:
                    if url not in seen_urls:
                        seen_urls.add(url)
                        product_urls.append(url)

            logger.info(f"[{site_key}] Total unique product URLs: {len(product_urls)}")

            # Phase 2: scrape each product page
            for product_url in product_urls:
                logger.info(f"[{site_key}] Product: {product_url}")
                html = await (fetch_html_js(product_url, delay) if requires_js
                              else fetch_html(session, product_url, delay))
                if not html:
                    continue
                soup    = BeautifulSoup(html, "lxml")
                product = extract_product(site_key, soup, product_url)
                if product:
                    products.append(product)
                    logger.info(f"[{site_key}] Extracted: {product['name']} — {product['price']}")
                else:
                    logger.warning(f"[{site_key}] Extraction failed for {product_url}")

    logger.info(f"[{site_key}] Done. {len(products)} products scraped.")
    return products


# ---------------------------------------------------------------------------
# Algolia / API-based scrapers registry
# Sites listed here bypass the HTML pipeline entirely.
# ---------------------------------------------------------------------------

ALGOLIA_SCRAPERS: dict = {}

try:
    from aritzia_scraper import scrape_aritzia
    ALGOLIA_SCRAPERS['aritzia'] = scrape_aritzia
    logger.debug("Aritzia Algolia scraper loaded.")
except ImportError:
    pass

try:
    from abercrombie_scraper import scrape_abercrombie
    ALGOLIA_SCRAPERS['abercrombie'] = scrape_abercrombie
    logger.debug("Abercrombie scraper loaded.")
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Scrape multiple sites concurrently
# ---------------------------------------------------------------------------

async def scrape_all(sites: dict) -> list[dict]:
    """
    Scrape all provided sites concurrently.
    Sites with a registered API scraper bypass the HTML pipeline.
    """
    tasks: list = []
    keys:  list = []

    for key, cfg in sites.items():
        if key in ALGOLIA_SCRAPERS:
            tasks.append(ALGOLIA_SCRAPERS[key]())
        else:
            tasks.append(scrape_site(key, cfg))
        keys.append(key)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_products: list[dict] = []
    for site_key, result in zip(keys, results):
        if isinstance(result, Exception):
            logger.error(f"[{site_key}] Scrape failed: {result}")
        else:
            logger.info(f"[{site_key}] {len(result)} products collected.")
            all_products.extend(result)

    return all_products
