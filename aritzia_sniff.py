import asyncio
from playwright.async_api import async_playwright

async def sniff():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'sec-ch-ua': '"Chromium";v="122", "Not(A:Brand";v="24"',
                'sec-ch-ua-platform': '"Windows"',
            }
        )
        page = await context.new_page()
        api_calls = []
        page.on('response', lambda r: api_calls.append(r.url) if any(x in r.url for x in ['demandware', 'api', 'search', 'product']) else None)

        try:
            await page.goto('https://www.aritzia.com/us/en/clothing', timeout=20000, wait_until='domcontentloaded')
            await page.wait_for_timeout(5000)
            title = await page.title()
            print('Page title:', title)
            print(f'API calls intercepted: {len(api_calls)}')
            for url in api_calls[:20]:
                print(url[:120])
        except Exception as e:
            print('Error:', e)
        finally:
            await browser.close()

asyncio.run(sniff())
