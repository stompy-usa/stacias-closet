import asyncio
import json
import re
from playwright.async_api import async_playwright

WOMENS_CATEGORIES = [
    ('womens-new-arrivals',      'New Arrivals'),
    ('womens-tops',              'Tops'),
    ('womens-dresses-rompers',   'Dresses'),
    ('womens-pants',             'Pants'),
    ('womens-jeans',             'Jeans'),
    ('womens-shorts',            'Shorts'),
    ('womens-jackets-coats',     'Jackets & Coats'),
    ('womens-sweaters-sweatshirts', 'Sweaters'),
    ('womens-skirts',            'Skirts'),
]

async def scrape_category(page, category_slug: str, category_label: str) -> list[dict]:
    url = f'https://www.abercrombie.com/shop/us/{category_slug}'
    print(f'\nLoading: {url}')

    try:
        await page.goto(url, timeout=30000, wait_until='domcontentloaded')
        # Wait for product grid to populate
        await page.wait_for_selector('[class*="product-card"], [class*="ProductCard"], [class*="product-tile"], [data-product-id]', timeout=15000)
        await page.wait_for_timeout(3000)  # extra settle time
    except Exception as e:
        print(f'  Warning: {e}')

    # --- Strategy 1: Apollo state (most reliable, structured data) ---
    apollo_products = await page.evaluate('''() => {
        const key = "APOLLO_STATE__catalog-mfe-web-service-CategoryPageFrontEnd-config";
        const state = window[key];
        if (!state) return null;

        const products = [];
        for (const [k, v] of Object.entries(state)) {
            if (v && typeof v === "object" && v.__typename === "Product") {
                products.push(v);
            }
        }
        return products.length > 0 ? products : null;
    }''')

    if apollo_products:
        print(f'  Apollo state: {len(apollo_products)} products found')
        with open(f'abercrombie_apollo_{category_slug}.json', 'w') as f:
            json.dump(apollo_products, f, indent=2)
        print(f'  Saved to abercrombie_apollo_{category_slug}.json')

        # Print first product shape
        p = apollo_products[0]
        print(f'  First product keys: {list(p.keys())}')
        for k, v in list(p.items())[:15]:
            print(f'    {k}: {str(v)[:100]}')
        return apollo_products

    # --- Strategy 2: Scrape fully rendered DOM ---
    print('  Apollo state empty, trying DOM scrape...')
    dom_products = await page.evaluate('''() => {
        const results = [];
        // Try multiple selector patterns
        const selectors = [
            "a[class*='product-card']",
            "div[class*='product-card'] a",
            "[data-product-id]",
            "a[href*='/shop/us/p/']",
        ];

        const seen = new Set();
        for (const sel of selectors) {
            document.querySelectorAll(sel).forEach(el => {
                const card  = el.closest("[class*='product']") || el;
                const href  = el.href || el.querySelector("a")?.href || "";
                if (!href || seen.has(href)) return;
                seen.add(href);

                const name  = card.querySelector("[class*='title'], [class*='name'], h2, h3, p")?.textContent?.trim();
                const price = card.querySelector("[class*='price'], [class*='Price']")?.textContent?.trim();
                const img   = card.querySelector("img");
                const imgSrc = img?.src || img?.dataset?.src || "";

                if (name && href.includes("/shop/us/p/")) {
                    results.push({ name, price: price || "N/A", img: imgSrc, url: href });
                }
            });
        }
        return results;
    }''')

    print(f'  DOM scrape: {len(dom_products)} products found')
    for p in dom_products[:3]:
        print(f'    {p["name"][:50]} | {p["price"]} | {p["url"][:60]}')

    return dom_products


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            extra_http_headers={'Accept-Language': 'en-US,en;q=0.9'}
        )
        page = await context.new_page()

        # Test with just new arrivals first
        results = await scrape_category(page, 'womens-new-arrivals', 'New Arrivals')
        print(f'\nTotal from new-arrivals: {len(results)}')

        await browser.close()

asyncio.run(main())
