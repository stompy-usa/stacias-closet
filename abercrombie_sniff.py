import asyncio
import json
from playwright.async_api import async_playwright

async def sniff():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
        )
        page = await context.new_page()

        api_calls = []

        async def on_response(response):
            url = response.url
            ct  = response.headers.get('content-type', '')
            # Capture anything that looks like product/search/API data
            if any(x in url.lower() for x in ['api', 'search', 'product', 'catalog', 'algolia', 'graphql', 'query', 'json']):
                api_calls.append({'url': url, 'content_type': ct})
            elif 'json' in ct:
                api_calls.append({'url': url, 'content_type': ct})

        page.on('response', on_response)

        try:
            await page.goto('https://www.abercrombie.com/shop/us/womens-new-arrivals', timeout=25000, wait_until='domcontentloaded')
            await page.wait_for_timeout(6000)
            title = await page.title()
            print(f'Page title: {title}')
            print(f'API calls intercepted: {len(api_calls)}')
            print()
            for c in api_calls[:30]:
                print(c['url'][:130])
        except Exception as e:
            print(f'Error: {e}')
        finally:
            await browser.close()

asyncio.run(sniff())
