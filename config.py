# config.py
# Central configuration for Stacia's Closet scraper.
# Edit PROXY_BASE and SITES to adjust targets and behaviour.

PROXY_BASE = "https://stacias-closet.rcookson80.workers.dev"

# ---------------------------------------------------------------------------
# Site definitions
# Each entry controls how a site is scraped:
#   listing_urls  — category pages to crawl for product links
#   product_url_pattern — substring that identifies a product detail page
#   requires_js   — True = use Playwright headless browser instead of aiohttp
#   request_delay — seconds between requests (be polite)
# ---------------------------------------------------------------------------

SITES = {
    "wayward": {
        "name": "Wayward Collection",
        "base_url": "https://waywardcollection.com",
        "listing_urls": [
            "https://waywardcollection.com/shop",
            "https://waywardcollection.com/tops",
            "https://waywardcollection.com/vintage-dresses",
            "https://waywardcollection.com/pants-and-skirts",
            "https://waywardcollection.com/outerwear",
            "https://waywardcollection.com/sets-and-jumpsuits",
            "https://waywardcollection.com/sweaters",
            "https://waywardcollection.com/sale",
        ],
        "product_url_pattern": "/shop/p/",
        "requires_js": False,
        "request_delay": 1.5,
    },
    "aritzia": {
        "name": "Aritzia",
        "base_url": "https://www.aritzia.com",
        # listing_urls not used — scraped via Algolia API (aritzia_scraper.py)
        "listing_urls": [],
        "product_url_pattern": "",
        "requires_js": False,
        "request_delay": 0,
    },
    "abercrombie": {
        "name": "Abercrombie & Fitch",
        "base_url": "https://www.abercrombie.com",
        # listing_urls not used — scraped via Playwright DOM (abercrombie_scraper.py)
        "listing_urls": [],
        "product_url_pattern": "",
        "requires_js": False,
        "request_delay": 0,
    },
}

# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------

# How often to run a full refresh (seconds). Default: 2 hours.
REFRESH_INTERVAL_SECONDS = 2 * 60 * 60

# Wayward runs every cycle; Aritzia + A&F every N cycles to reduce bot detection risk.
HEAVY_SITE_CYCLE_INTERVAL = 2  # scrape Aritzia/A&F every 2nd refresh

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DB_PATH = "data/products.db"

# ---------------------------------------------------------------------------
# Playwright settings (for JS-heavy sites)
# ---------------------------------------------------------------------------

PLAYWRIGHT_TIMEOUT_MS = 20_000       # page load timeout
PLAYWRIGHT_WAIT_SELECTOR = "body"    # wait for this selector before scraping
