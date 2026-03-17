# product_extractor.py
# Per-site BeautifulSoup parsers.
# Each extract_* function receives a BeautifulSoup object and the page URL,
# and returns a list of Product dicts (or an empty list on failure).
#
# Product dict shape:
# {
#   "site":        str   — site key from config.SITES
#   "name":        str   — product name
#   "price":       str   — price as displayed (e.g. "$128.00")
#   "image_url":   str   — absolute URL to the primary product image
#   "product_url": str   — absolute URL to the product page
#   "category":    str   — category label (best-effort)
#   "scraped_at":  str   — ISO 8601 timestamp (added by db.py)
# }

import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Wayward Collection (Squarespace)
#
# Squarespace renders ALL product data (name, price, images) inline on the
# listing page — there are no individual product detail page links in the
# static HTML. Strategy: extract everything from listing pages directly.
#
# HTML structure observed:
#   .ProductList-item  or  .grid-item  wraps each product
#     h1 / .ProductList-item-title  — product name
#     .sqs-money-native or [data-currency-value] — price
#     img[data-src] or img[src] inside .ProductList-item-image — primary image
#     <a href> on the item wrapper — links to individual product page
# ---------------------------------------------------------------------------

def extract_wayward_listings(soup: BeautifulSoup, page_url: str) -> list[str]:
    """
    Wayward is a direct-extract site — return an empty list so scraper.py
    skips the product-page crawl phase. Products are extracted inline by
    extract_wayward_products_from_listing() instead.
    """
    return []


def extract_wayward_products_from_listing(soup: BeautifulSoup, page_url: str) -> list[dict]:
    """
    Extract all products directly from a Wayward listing page.
    Squarespace item wrappers tried in order: .ProductList-item, .grid-item,
    and a fallback that zips h1 titles with nearby prices.
    """
    products = []
    category = _infer_category_from_url(page_url)

    # --- Strategy 1: Squarespace .ProductList-item wrappers ---
    items = soup.select(".ProductList-item")

    # --- Strategy 2: generic .grid-item ---
    if not items:
        items = soup.select(".grid-item")

    for item in items:
        try:
            # Name
            name_el = (
                item.select_one(".ProductList-item-title")
                or item.select_one("h1")
                or item.select_one("h2")
                or item.select_one("[class*='title']")
            )
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            if not name:
                continue

            # Price
            price_el = (
                item.select_one(".sqs-money-native")
                or item.select_one("[data-currency-value]")
                or item.select_one("[class*='price']")
            )
            if price_el:
                if price_el.has_attr("data-currency-value"):
                    price_str = f"${price_el['data-currency-value']}"
                else:
                    price_str = price_el.get_text(strip=True)
            else:
                price_str = "N/A"

            # Image — Squarespace lazy-loads via data-src
            img_el = item.select_one("img")
            image_url = ""
            if img_el:
                image_url = (
                    img_el.get("data-src")
                    or img_el.get("data-lazy-src")
                    or img_el.get("src")
                    or ""
                )
                if image_url.startswith("//"):
                    image_url = "https:" + image_url
                # Strip Squarespace resize params to get full image
                image_url = image_url.split("?")[0]

            # Product URL — the item wrapper or its first <a>
            link_el = item.select_one("a[href]")
            if link_el:
                product_url = urljoin("https://waywardcollection.com", link_el["href"])
            else:
                product_url = page_url  # fallback to listing URL

            products.append({
                "site": "wayward",
                "name": name,
                "price": price_str,
                "image_url": image_url,
                "product_url": product_url,
                "category": category,
            })

        except Exception:
            continue

    # --- Strategy 3: fallback — zip h1 headings with price elements ---
    # Used when Squarespace renders without standard item wrappers.
    if not products:
        names = soup.select("h1")
        prices = soup.select(".sqs-money-native, [data-currency-value]")
        images = soup.select("img[data-src], img[src]")

        for i, name_el in enumerate(names):
            name = name_el.get_text(strip=True)
            if not name or len(name) < 3:
                continue

            price_str = "N/A"
            if i < len(prices):
                p = prices[i]
                price_str = f"${p['data-currency-value']}" if p.has_attr("data-currency-value") else p.get_text(strip=True)

            image_url = ""
            if i < len(images):
                img = images[i]
                image_url = img.get("data-src") or img.get("src") or ""
                if image_url.startswith("//"):
                    image_url = "https:" + image_url
                image_url = image_url.split("?")[0]

            products.append({
                "site": "wayward",
                "name": name,
                "price": price_str,
                "image_url": image_url,
                "product_url": page_url,
                "category": category,
            })

    return products


def extract_wayward_product(soup: BeautifulSoup, page_url: str) -> dict | None:
    """Not used — Wayward products are extracted from listing pages directly."""
    return None


# ---------------------------------------------------------------------------
# Aritzia
# ---------------------------------------------------------------------------

def extract_aritzia_listings(soup: BeautifulSoup, page_url: str) -> list[str]:
    """Return product page URLs found on an Aritzia listing page."""
    links = []
    for a in soup.select("a[href]"):
        href = a["href"]
        if "/en/product/" in href:
            full = urljoin("https://www.aritzia.com", href).split("?")[0]
            if full not in links:
                links.append(full)
    return links


def extract_aritzia_product(soup: BeautifulSoup, page_url: str) -> dict | None:
    """Parse a single Aritzia product page."""
    try:
        name = soup.select_one("h1[class*='product-name'], h1[class*='ProductName'], h1")
        price = (
            soup.select_one("[class*='product-price'] [class*='sale']")
            or soup.select_one("[class*='product-price']")
            or soup.select_one("[class*='ProductPrice']")
        )

        img = (
            soup.select_one("img[class*='primary'], img[class*='ProductImage']")
            or soup.select_one(".product-images img")
            or soup.select_one("img[data-src]")
        )
        image_url = ""
        if img:
            image_url = img.get("data-src") or img.get("src") or ""
            if image_url.startswith("//"):
                image_url = "https:" + image_url

        if not name or not image_url:
            return None

        return {
            "site": "aritzia",
            "name": name.get_text(strip=True),
            "price": price.get_text(strip=True) if price else "N/A",
            "image_url": image_url,
            "product_url": page_url,
            "category": _infer_category_from_url(page_url),
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Abercrombie & Fitch
# ---------------------------------------------------------------------------

def extract_abercrombie_listings(soup: BeautifulSoup, page_url: str) -> list[str]:
    """Return product page URLs found on an A&F listing page."""
    links = []
    for a in soup.select("a[href]"):
        href = a["href"]
        if "/shop/us/p/" in href:
            full = urljoin("https://www.abercrombie.com", href).split("?")[0]
            if full not in links:
                links.append(full)
    return links


def extract_abercrombie_product(soup: BeautifulSoup, page_url: str) -> dict | None:
    """Parse a single A&F product page."""
    try:
        name = soup.select_one("h1[class*='product-title'], h1[class*='ProductTitle'], h1")
        price = (
            soup.select_one("[class*='product-price-sale']")
            or soup.select_one("[class*='product-price']")
        )

        img = (
            soup.select_one("img[class*='product-image-main']")
            or soup.select_one("img[class*='ProductImage']")
            or soup.select_one(".product-image-container img")
        )
        image_url = ""
        if img:
            image_url = img.get("data-src") or img.get("src") or ""
            if image_url.startswith("//"):
                image_url = "https:" + image_url

        if not name or not image_url:
            return None

        return {
            "site": "abercrombie",
            "name": name.get_text(strip=True),
            "price": price.get_text(strip=True) if price else "N/A",
            "image_url": image_url,
            "product_url": page_url,
            "category": _infer_category_from_url(page_url),
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Router — call the right extractor for a given site key
# ---------------------------------------------------------------------------

LISTING_EXTRACTORS = {
    "wayward":     extract_wayward_listings,       # returns [] — direct-extract site
    "aritzia":     extract_aritzia_listings,
    "abercrombie": extract_abercrombie_listings,
}

PRODUCT_EXTRACTORS = {
    "wayward":     extract_wayward_product,        # returns None — not used
    "aritzia":     extract_aritzia_product,
    "abercrombie": extract_abercrombie_product,
}

# Sites where products live on listing pages (no individual product pages needed)
LISTING_DIRECT_EXTRACTORS = {
    "wayward": extract_wayward_products_from_listing,
}


def extract_product_links(site_key: str, soup: BeautifulSoup, page_url: str) -> list[str]:
    fn = LISTING_EXTRACTORS.get(site_key)
    return fn(soup, page_url) if fn else []


def extract_product(site_key: str, soup: BeautifulSoup, page_url: str) -> dict | None:
    fn = PRODUCT_EXTRACTORS.get(site_key)
    return fn(soup, page_url) if fn else None


def extract_products_from_listing(site_key: str, soup: BeautifulSoup, page_url: str) -> list[dict]:
    """For direct-extract sites — pull all products from a listing page."""
    fn = LISTING_DIRECT_EXTRACTORS.get(site_key)
    return fn(soup, page_url) if fn else []


def is_direct_extract(site_key: str) -> bool:
    """Returns True if this site extracts products directly from listing pages."""
    return site_key in LISTING_DIRECT_EXTRACTORS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _infer_category_from_url(url: str) -> str:
    """Best-effort category label from URL path segments."""
    segments = url.rstrip("/").split("/")
    keywords = [
        "dress", "top", "pant", "skirt", "jacket", "coat",
        "outerwear", "sweater", "knit", "jean", "sale",
        "new-arrival", "set", "jumpsuit",
    ]
    for seg in reversed(segments):
        seg_lower = seg.lower()
        for kw in keywords:
            if kw in seg_lower:
                return seg_lower.replace("-", " ").title()
    return "Other"
