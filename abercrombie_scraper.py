import asyncio
import logging
import re
from playwright.async_api import async_playwright, Browser

logger = logging.getLogger(__name__)

IMAGE_BASE   = 'https://img.abercrombie.com/is/image/anf/'
PRODUCT_BASE = 'https://www.abercrombie.com'

WOMENS_CATEGORIES = [
    ('womens-new-arrivals',                      'New Arrivals'),
    ('womens-tops--1',                           'Tops'),
    ('womens-bottoms--1',                        'Bottoms'),
    ('womens-dresses-and-jumpsuits',             'Dresses & Jumpsuits'),
    ('womens-coats-and-jackets',                 'Coats & Jackets'),
    ('womens-activewear',                        'Activewear'),
    ('womens-matching-sets-dresses-and-rompers', 'Sets & Rompers'),
    ('womens-swim',                              'Swim'),
    ('womens-sleep-and-intimates',               'Sleep & Intimates'),
]


def _clean_price(raw: str) -> str:
    """'$65$65' or '$65$48.90' → keep the sale price (first occurrence)."""
    if not raw:
        return 'N/A'
    prices = re.findall(r'\$[\d,]+(?:\.\d{2})?', raw)
    if not prices:
        return raw.strip()
    # If two prices shown, second is usually sale — return cheaper
    if len(prices) >= 2:
        vals = [float(p.replace('$','').replace(',','')) for p in prices]
        return f'${min(vals):.0f}'
    return prices[0]


def _clean_product_url(url: str) -> str:
    """Strip tracking params from product URL."""
    return url.split('?')[0] if url else ''


async def scrape_category(browser: Browser, category_slug: str, category_label: str) -> list[dict]:
    """Scrape one A&F women's category page and return normalised product dicts."""
    page = await browser.new_page()
    products = []
    seen_urls: set[str] = set()

    try:
        url = f'https://www.abercrombie.com/shop/us/{category_slug}'
        logger.info(f'[abercrombie] Loading: {url}')

        await page.goto(url, timeout=30000, wait_until='domcontentloaded')

        # Wait for product links to appear
        try:
            await page.wait_for_selector("a[href*='/shop/us/p/']", timeout=30000)
        except Exception:
            logger.warning(f'[abercrombie] No product links found on {url}')
            return []

        # Scroll to trigger all lazy-loaded images
        # Slower scroll with longer pauses gives images time to swap in
        for _ in range(8):
            await page.evaluate('window.scrollBy(0, window.innerHeight)')
            await page.wait_for_timeout(2000)  # 2s per scroll = images have time to load
        # Scroll back to top then do a final full-page sweep
        await page.evaluate('window.scrollTo(0, 0)')
        await page.wait_for_timeout(1000)
        for _ in range(8):
            await page.evaluate('window.scrollBy(0, window.innerHeight)')
            await page.wait_for_timeout(1500)
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await page.wait_for_timeout(3000)  # final settle time

        # Extract all product data from DOM
        raw_products = await page.evaluate('''() => {
            const results = [];
            const seen    = new Set();

            // Each product card has multiple <a> tags (image link + text link)
            // Group by clean URL to avoid duplicates within the page
            const cardMap = new Map();

            document.querySelectorAll("a[href*='/shop/us/p/']").forEach(a => {
                const cleanUrl = a.href.split("?")[0];
                if (!cleanUrl || cleanUrl === window.location.href.split("?")[0]) return;

                if (!cardMap.has(cleanUrl)) {
                    cardMap.set(cleanUrl, { url: cleanUrl, name: null, price: null, img: null });
                }
                const entry = cardMap.get(cleanUrl);

                // Name — look for text content with product name
                const text = a.textContent.trim();
                if (text && text.length > 3 && !text.startsWith('$') && !entry.name) {
                    // Strip price from text if appended
                    const nameOnly = text.replace(/\\$[\\d,.]+/g, '').trim();
                    if (nameOnly.length > 3) entry.name = nameOnly;
                }

                // Price — find within the card container
                if (!entry.price) {
                    const card  = a.closest("[class*='product']") || a.parentElement;
                    const priceEl = card?.querySelector("[class*='price'], [class*='Price']");
                    if (priceEl) entry.price = priceEl.textContent.trim();
                }

                // Image — find within card
                if (!entry.img) {
                    const card = a.closest("[class*='product']") || a.parentElement;
                    const img  = card?.querySelector("img[src*='img.abercrombie.com']") ||
                                 card?.querySelector("img[data-src*='img.abercrombie.com']") ||
                                 card?.querySelector("img");
                    if (img) {
                        // src may be a base64 placeholder if image is lazy-loaded
                        // check data-src, data-lazy-src, and srcset as fallbacks
                        const candidates = [
                            img.dataset.src,
                            img.dataset.lazySrc,
                            img.dataset.originalSrc,
                            img.src,
                            (img.srcset || img.dataset.srcset || "").split(",")[0].trim().split(" ")[0],
                        ];
                        const realUrl = candidates.find(c => c && !c.startsWith("data:") && c.includes("abercrombie")) || "";
                        entry.img = realUrl
                            .replace("product-xsmall", "product-large")
                            .replace("product-small",  "product-large")
                            .replace("product-medium", "product-large");
                    }
                }
            });

            cardMap.forEach(v => {
                if (v.name && v.url) results.push(v);
            });

            return results;
        }''')

        logger.info(f'[abercrombie] {category_label}: {len(raw_products)} products extracted')

        for rp in raw_products:
            clean_url = _clean_product_url(rp['url'])
            if clean_url in seen_urls:
                continue
            seen_urls.add(clean_url)

            # Clean up name — remove "Bestseller", "New", badge text
            name = re.sub(r'^(Bestseller|New|Sale|Clearance)\s*', '', rp['name'] or '', flags=re.I).strip()
            if not name:
                continue

            products.append({
                'site':        'abercrombie',
                'name':        name,
                'price':       _clean_price(rp.get('price', '')),
                'image_url':   rp.get('img', ''),
                'product_url': clean_url,
                'category':    category_label,
            })

    except Exception as e:
        logger.error(f'[abercrombie] Error on {category_slug}: {e}')
    finally:
        await page.close()

    return products


async def scrape_abercrombie() -> list[dict]:
    """Scrape all women's categories and return combined deduplicated product list."""
    all_products: list[dict] = []
    seen_urls:    set[str]   = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/122.0.0.0 Safari/537.36'
            ),
            extra_http_headers={'Accept-Language': 'en-US,en;q=0.9'},
        )

        for slug, label in WOMENS_CATEGORIES:
            products = await scrape_category(context, slug, label)
            for p in products:
                if p['product_url'] not in seen_urls:
                    seen_urls.add(p['product_url'])
                    all_products.append(p)
            # Polite delay between categories
            await asyncio.sleep(2)

        await context.close()

    logger.info(f'[abercrombie] Total unique products: {len(all_products)}')
    return all_products


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    async def test():
        products = await scrape_abercrombie()
        print(f'\nTotal products: {len(products)}')
        print('\nSample:')
        for p in products[:8]:
            print(f"  {p['name'][:45]:<45} | {p['price']:<10} | {p['category']:<20} | {p['image_url'][:55]}")

    asyncio.run(test())
