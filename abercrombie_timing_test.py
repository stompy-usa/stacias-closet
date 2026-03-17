import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        )
        page = await context.new_page()
        await page.goto('https://www.abercrombie.com/shop/us/womens-tops',
                        timeout=30000, wait_until='domcontentloaded')

        # Poll every 2 seconds up to 20 seconds, report when products appear
        for i in range(10):
            await page.wait_for_timeout(2000)
            count = await page.evaluate(
                "() => document.querySelectorAll(\"a[href*='/shop/us/p/']\").length"
            )
            print(f'{(i+1)*2}s: {count} product links')
            if count > 0:
                break

        await context.close()

asyncio.run(test())
