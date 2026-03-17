import asyncio
import json
import re
from playwright.async_api import async_playwright

async def extract_ssr():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            extra_http_headers={'Accept-Language': 'en-US,en;q=0.9'}
        )
        page = await context.new_page()

        try:
            await page.goto('https://www.abercrombie.com/shop/us/womens-new-arrivals', timeout=25000, wait_until='domcontentloaded')
            await page.wait_for_timeout(6000)

            # --- Strategy 1: look for __NEXT_DATA__ (Next.js SSR) ---
            next_data = await page.evaluate('''() => {
                const el = document.getElementById("__NEXT_DATA__");
                return el ? el.textContent : null;
            }''')

            if next_data:
                print('Found __NEXT_DATA__!')
                data = json.loads(next_data)
                with open('abercrombie_next_data.json', 'w') as f:
                    json.dump(data, f, indent=2)
                print(f'Saved to abercrombie_next_data.json ({len(next_data)} chars)')

                # Try to find products within
                data_str = json.dumps(data)
                print(f'Contains "price": {"price" in data_str.lower()}')
                print(f'Contains "productName": {"productname" in data_str.lower()}')

                # Print top-level keys
                print(f'Top keys: {list(data.keys())}')
                if 'props' in data:
                    print(f'props keys: {list(data["props"].keys())}')
                    if 'pageProps' in data['props']:
                        print(f'pageProps keys: {list(data["props"]["pageProps"].keys())[:10]}')

            else:
                print('No __NEXT_DATA__ found')

            # --- Strategy 2: look for window state objects ---
            win_keys = await page.evaluate('''() => {
                return Object.keys(window).filter(k =>
                    k.includes('STATE') || k.includes('REDUX') ||
                    k.includes('DATA') || k.includes('STORE') ||
                    k.includes('INITIAL') || k.includes('PRELOADED')
                );
            }''')
            print(f'\nWindow state keys found: {win_keys}')

            # --- Strategy 3: find product data in DOM directly ---
            products_from_dom = await page.evaluate('''() => {
                // Look for product cards in the DOM
                const cards = document.querySelectorAll("[class*=product-grid-item], [class*=ProductGrid], [data-product-id], [class*=product-tile]");
                const results = [];
                cards.forEach(card => {
                    const name  = card.querySelector("[class*=product-title], [class*=ProductTitle], h2, h3");
                    const price = card.querySelector("[class*=price], [class*=Price]");
                    const img   = card.querySelector("img");
                    const link  = card.querySelector("a[href]");
                    if (name || price) {
                        results.push({
                            name:  name  ? name.textContent.trim()  : null,
                            price: price ? price.textContent.trim() : null,
                            img:   img   ? (img.src || img.dataset.src) : null,
                            url:   link  ? link.href : null,
                        });
                    }
                });
                return results;
            }''')

            print(f'\nProducts found in DOM: {len(products_from_dom)}')
            for p in products_from_dom[:5]:
                print(f'  {p}')

        except Exception as e:
            print(f'Error: {e}')
        finally:
            await browser.close()

asyncio.run(extract_ssr())
