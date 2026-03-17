import asyncio
import json
from playwright.async_api import async_playwright

async def capture_algolia():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
            }
        )
        page = await context.new_page()

        algolia_requests  = []
        algolia_responses = []

        async def on_request(request):
            if 'search-0.aritzia.com' in request.url or 'algolia' in request.url.lower():
                algolia_requests.append({
                    'url':     request.url,
                    'headers': dict(request.headers),
                    'body':    request.post_data,
                })

        async def on_response(response):
            if 'search-0.aritzia.com' in response.url or 'algolia' in response.url.lower():
                try:
                    body = await response.json()
                    algolia_responses.append({
                        'url':  response.url,
                        'body': body,
                    })
                except Exception:
                    pass

        page.on('request',  on_request)
        page.on('response', on_response)

        try:
            await page.goto('https://www.aritzia.com/us/en/clothing', timeout=25000, wait_until='domcontentloaded')
            await page.wait_for_timeout(6000)
        except Exception as e:
            print(f'Page load note: {e}')
        finally:
            await browser.close()

        # Save full captured data
        with open('algolia_capture.json', 'w', encoding='utf-8') as f:
            json.dump({
                'requests':  algolia_requests,
                'responses': algolia_responses,
            }, f, indent=2)

        print(f'Captured {len(algolia_requests)} Algolia requests, {len(algolia_responses)} responses')

        # Print request headers (this is where the API key lives)
        for req in algolia_requests[:2]:
            print('\n--- REQUEST URL ---')
            print(req['url'][:120])
            print('--- HEADERS ---')
            for k, v in req['headers'].items():
                if 'algolia' in k.lower() or 'x-' in k.lower():
                    print(f'  {k}: {v}')
            print('--- BODY (first 500 chars) ---')
            print(str(req['body'])[:500])

        # Print shape of first response
        for resp in algolia_responses[:1]:
            print('\n--- RESPONSE SHAPE ---')
            body = resp['body']
            if 'results' in body:
                first = body['results'][0]
                print(f"Total hits: {first.get('nbHits')}")
                print(f"Hits per page: {first.get('hitsPerPage')}")
                if first.get('hits'):
                    print('\nFirst product keys:', list(first['hits'][0].keys()))
                    print('\nFirst product sample:')
                    hit = first['hits'][0]
                    for key in ['name', 'price', 'images', 'image', 'url', 'productUrl', 'category']:
                        if key in hit:
                            print(f'  {key}: {str(hit[key])[:100]}')

asyncio.run(capture_algolia())
