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

        json_calls = []
        all_calls  = []

        async def on_response(response):
            url = response.url
            ct  = response.headers.get('content-type', '')
            all_calls.append(url)

            # Capture JSON responses only
            if 'json' in ct:
                try:
                    body = await response.json()
                    json_calls.append({'url': url, 'body': body})
                except Exception:
                    pass

        page.on('response', on_response)

        try:
            await page.goto('https://www.abercrombie.com/shop/us/womens-new-arrivals', timeout=25000, wait_until='domcontentloaded')
            await page.wait_for_timeout(8000)
        except Exception as e:
            print(f'Load note: {e}')
        finally:
            await browser.close()

        # Save all JSON responses
        with open('abercrombie_json_calls.json', 'w') as f:
            json.dump(json_calls, f, indent=2)

        print(f'Total network calls: {len(all_calls)}')
        print(f'JSON responses captured: {len(json_calls)}')
        print()

        # Print JSON call URLs and a shape preview
        for call in json_calls:
            url  = call['url']
            body = call['body']
            print(f'URL: {url[:120]}')

            # Try to detect product data
            if isinstance(body, dict):
                keys = list(body.keys())[:8]
                print(f'  Keys: {keys}')
                # Look for product arrays
                for k, v in body.items():
                    if isinstance(v, list) and len(v) > 0:
                        print(f'  [{k}] = list of {len(v)}, first item keys: {list(v[0].keys())[:6] if isinstance(v[0], dict) else type(v[0]).__name__}')
            elif isinstance(body, list):
                print(f'  Array of {len(body)}, first item keys: {list(body[0].keys())[:6] if body and isinstance(body[0], dict) else "?"}')
            print()

asyncio.run(capture())
