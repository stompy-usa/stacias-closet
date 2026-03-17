import asyncio
from playwright.async_api import async_playwright

async def test_stealth():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ]
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 800},
            locale='en-US',
            timezone_id='America/New_York',
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'sec-ch-ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
            }
        )

        # Patch navigator.webdriver = false
        await context.add_init_script('''
            Object.defineProperty(navigator, "webdriver", { get: () => undefined });
            Object.defineProperty(navigator, "plugins", { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, "languages", { get: () => ["en-US", "en"] });
            window.chrome = { runtime: {} };
        ''')

        # Try playwright-stealth if installed
        try:
            from playwright_stealth import stealth_async
            page = await context.new_page()
            await stealth_async(page)
            print('playwright-stealth applied')
        except ImportError:
            page = await context.new_page()
            print('playwright-stealth not installed, using manual patches only')

        await page.goto('https://www.abercrombie.com/shop/us/womens-tops',
                        timeout=30000, wait_until='domcontentloaded')
        await page.wait_for_timeout(8000)

        count   = await page.evaluate("() => document.querySelectorAll(\"a[href*='/shop/us/p/']\").length")
        preview = await page.evaluate("() => document.body.innerText.slice(0, 200)")

        print(f'Product links: {count}')
        print(f'Body preview: {preview}')

        await browser.close()

asyncio.run(test_stealth())
