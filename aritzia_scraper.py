import asyncio
import aiohttp
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── Algolia credentials (public search-only key, sent to every browser visitor) ──
ALGOLIA_APP_ID  = 'SONLJM8OH6'
ALGOLIA_API_KEY = '1455bca7c6c33e746a0f38beb28422e6'
ALGOLIA_INDEX   = 'production_ecommerce_aritzia__Aritzia_US__products__en_US'
ALGOLIA_URL     = f'https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query'

ALGOLIA_HEADERS = {
    'x-algolia-application-id': ALGOLIA_APP_ID,
    'x-algolia-api-key':        ALGOLIA_API_KEY,
    'Content-Type':             'application/json',
}

IMAGE_BASE = 'https://assets.aritzia.com/image/upload'
PRODUCT_BASE = 'https://www.aritzia.com/us/en/product'

# How many products to fetch per Algolia page (max 1000, 96 matches their site)
PAGE_SIZE = 96

# Categories to pull — maps Aritzia category ID → our normalised label
CATEGORY_MAP = {
    'clothing':       'All Clothing',
    'tops':           'Tops',
    'dresses':        'Dresses',
    'pants':          'Pants',
    'jackets-coats':  'Jackets & Coats',
    'skirts':         'Skirts',
    'sweaters-knits': 'Sweaters & Knits',
    'shorts':         'Shorts',
    'jumpsuits':      'Jumpsuits',
}


def _build_image_url(default_image: str) -> str:
    """Convert an Aritzia image code to a full CDN URL."""
    if not default_image:
        return ''
    return f'{IMAGE_BASE}/{default_image}.jpg'


def _build_product_url(slug: str) -> str:
    """Convert a slug to a full product URL."""
    if not slug:
        return ''
    return f'{PRODUCT_BASE}/{slug}'


def _extract_price(hit: dict) -> str:
    """Return a formatted price string, showing sale price if applicable."""
    price = hit.get('price', {})
    on_sale = hit.get('onSale', False)
    try:
        if on_sale:
            low  = price.get('min', 0)
            high = price.get('max', 0)
            return f'${low:.0f} (was ${high:.0f})'
        else:
            return f'${price.get("max", 0):.0f}'
    except Exception:
        return 'N/A'


def _normalise_hit(hit: dict) -> dict | None:
    """Convert a raw Algolia hit into our standard product dict."""
    try:
        name = hit.get('c_displayName', '').strip()
        if not name:
            return None

        slug       = hit.get('slug', '')
        image_code = hit.get('defaultImage', '')

        product_url = _build_product_url(slug)
        image_url   = _build_image_url(image_code)

        if not product_url or not image_url:
            return None

        # subDept is always a clean garment type (e.g. ['Pant'], ['T-shirt'])
        # primaryCategoryId can be a campaign slug — only use as fallback
        sub_dept = hit.get('subDept', [])
        if sub_dept:
            category = sub_dept[0].strip()
        else:
            category_id = hit.get('primaryCategoryId', 'clothing')
            category    = CATEGORY_MAP.get(category_id, category_id.replace('-', ' ').title())

        return {
            'site':        'aritzia',
            'name':        name,
            'price':       _extract_price(hit),
            'image_url':   image_url,
            'product_url': product_url,
            'category':    category,
        }
    except Exception:
        return None


async def fetch_page(session: aiohttp.ClientSession, category: str, page: int) -> tuple[list[dict], int]:
    """Fetch one page of results for a category. Returns (hits, total_pages)."""
    payload = {
        'query':       '',
        'filters':     f'categories:{category}',
        'hitsPerPage': PAGE_SIZE,
        'page':        page,
    }
    try:
        async with session.post(ALGOLIA_URL, headers=ALGOLIA_HEADERS, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                logger.warning(f'[aritzia] Algolia returned {resp.status} for category={category} page={page}')
                return [], 0
            data = await resp.json()
            return data.get('hits', []), data.get('nbPages', 0)
    except Exception as e:
        logger.error(f'[aritzia] Fetch error category={category} page={page}: {e}')
        return [], 0


async def scrape_aritzia() -> list[dict]:
    """
    Pull all clothing products from Aritzia via Algolia.
    Queries the top-level 'clothing' category which contains everything,
    then paginates through all results.
    """
    products   = []
    seen_ids:  set[str] = set()

    async with aiohttp.ClientSession() as session:
        # First request to find total page count
        first_hits, total_pages = await fetch_page(session, 'clothing', 0)
        logger.info(f'[aritzia] Total pages: {total_pages}')

        all_hits = list(first_hits)

        # Fetch remaining pages concurrently in batches of 5
        for batch_start in range(1, total_pages, 5):
            batch = range(batch_start, min(batch_start + 5, total_pages))
            tasks = [fetch_page(session, 'clothing', p) for p in batch]
            results = await asyncio.gather(*tasks)
            for hits, _ in results:
                all_hits.extend(hits)
            await asyncio.sleep(0.5)  # brief pause between batches

        logger.info(f'[aritzia] Total raw hits: {len(all_hits)}')

        for hit in all_hits:
            # Deduplicate by masterId — Algolia returns one entry per colour variant
            master_id = hit.get('masterId') or hit.get('objectID', '')
            if master_id in seen_ids:
                continue
            seen_ids.add(master_id)

            product = _normalise_hit(hit)
            if product:
                products.append(product)

    logger.info(f'[aritzia] Done. {len(products)} unique products.')
    return products


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    async def test():
        products = await scrape_aritzia()
        print(f'\nTotal products: {len(products)}')
        print('\nSample products:')
        for p in products[:5]:
            print(f"  {p['name'][:45]:<45} | {p['price']:<18} | {p['category']:<20} | {p['image_url'][:50]}")

    asyncio.run(test())
