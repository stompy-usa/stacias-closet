import asyncio
from playwright.async_api import async_playwright

CANDIDATES = [
    'womens-tops--1',
    'womens-dresses-rompers--1',
    'womens-pants--1',
    'womens-jeans--1',
    'womens-shorts--1',
    'womens-jackets-coats--1',
    'womens-sweaters-sweatshirts--1',
    'womens-skirts--1',
    'womens-activewear--1',
    'womens-new-arrivals--1',
]

async def check():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        )
        await context.add_init_script(
            'Object.defineProperty(navigator, "webdriver", { get: () => undefined });'
        )

        for slug in CANDIDATES:
            page = await context.new_page()
            url  = f'https://www.abercrombie.com/shop/us/{slug}'
            try:
                await page.goto(url, timeout=20000, wait_until='domcontentloaded')
                await page.wait_for_timeout(8000)
                count   = await page.evaluate("() => document.querySelectorAll(\"a[href*='/shop/us/p/']\").length")
                captcha = await page.evaluate("() => document.body.innerText.includes('CAPTCHA') || document.body.innerText.includes('characters seen')")
                status  = 'CAPTCHA' if captcha else f'{count} products'
                print(f'{slug:<45} → {status}')
            except Exception as e:
                print(f'{slug:<45} → ERROR: {str(e)[:50]}')
            finally:
                await page.close()

        await context.close()

asyncio.run(check())
