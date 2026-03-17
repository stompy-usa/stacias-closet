import asyncio
import json
from playwright.async_api import async_playwright

async def capture():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            extra_http_headers={'Accept-Language': 'en-US,en;q=0.9'}
        )
        page = await context.new_page()

        catalog_calls = []

        async def on_response(response):
            url = response.url
            if '/api/bff/catalog' in url:
                try:
                    body = await response.json()
                    catalog_calls.append({'url': url, 'body': body})
                    print(f'Captured catalog call: {url[:130]}')
                except Exception as e:
                    print(f'Failed to parse: {e}')

        page.on('response', on_response)

        try:
            await page.goto('https://www.abercrombie.com/shop/us/womens-new-arrivals', timeout=25000, wait_until='domcontentloaded')
            await page.wait_for_timeout(8000)
        except Exception as e:
            print(f'Load note: {e}')
        finally:
            await browser.close()

        print(f'\nTotal catalog calls: {len(catalog_calls)}')

        for i, call in enumerate(catalog_calls):
            print(f'\n=== CALL {i+1} ===')
            print(f'URL: {call["url"]}')
            body = call['body']

            # Drill into the data structure
            if isinstance(body, list):
                for item in body:
                    if isinstance(item, dict) and 'data' in item:
                        data = item['data']
                        print(f'data type: {type(data).__name__}')
                        if isinstance(data, dict):
                            print(f'data keys: {list(data.keys())}')
                            # Look for product arrays
                            for k, v in data.items():
                                if isinstance(v, list) and len(v) > 0:
                                    print(f'  data[{k}] = list of {len(v)}')
                                    if isinstance(v[0], dict):
                                        print(f'    first item keys: {list(v[0].keys())}')
                                        # Print first product sample
                                        if any(x in str(list(v[0].keys())).lower() for x in ['name', 'price', 'product', 'image']):
                                            print(f'    PRODUCT DATA FOUND! Sample:')
                                            for pk, pv in list(v[0].items())[:12]:
                                                print(f'      {pk}: {str(pv)[:100]}')
                        elif isinstance(data, list):
                            print(f'data is list of {len(data)}')
                            if data and isinstance(data[0], dict):
                                print(f'first item keys: {list(data[0].keys())}')

        # Save full response for inspection
        with open('abercrombie_catalog.json', 'w') as f:
            json.dump(catalog_calls, f, indent=2)
        print('\nFull response saved to abercrombie_catalog.json')

asyncio.run(capture())
