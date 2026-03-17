import asyncio
from playwright.async_api import async_playwright

# Candidate slugs to test — A&F URL patterns can be inconsistent
CANDIDATES = [
    'womens-tops',
    'womens-clothing-tops',
    'womens-shirts-tops',
    'womens-new-tops',
    'womens-dresses-rompers',
    'womens-dresses',
    'womens-pants',
    'womens-pants-trousers',
    'womens-jeans',
    'womens-denim',
    'womens-shorts',
    'womens-jackets-coats',
    'womens-jackets',
    'womens-outerwear',
    'womens-sweaters-sweatshirts',
    'womens-sweaters',
    'womens-sweatshirts-hoodies',
    'womens-skirts',
]

async def check_slugs():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        )

        for slug in CANDIDATES:
            page = await context.new_page()
            url  = f'https://www.abercrombie.com/shop/us/{slug}'
            try:
                resp = await page.goto(url, timeout=12000, wait_until='domcontentloaded')
                status = resp.status if resp else '?'
                # Quick check — wait just 3s, see if any product links appear
                await page.wait_for_timeout(3000)
                count = await page.evaluate('''() =>
                    document.querySelectorAll("a[href*='/shop/us/p/']").length
                ''')
                final_url = page.url
                redirected = '→ REDIRECTED' if slug not in final_url else ''
                print(f'[{status}] {slug:<40} products={count:>3}  {redirected}')
            except Exception as e:
                print(f'[ERR] {slug:<40} {str(e)[:60]}')
            finally:
                await page.close()

        await context.close()

asyncio.run(check_slugs())
