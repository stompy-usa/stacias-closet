import asyncio, aiohttp, json

APP_ID  = 'SONLJM8OH6'
API_KEY = '1455bca7c6c33e746a0f38beb28422e6'
INDEX   = 'production_ecommerce_aritzia__Aritzia_US__products__en_US'

URL = f'https://{APP_ID}-dsn.algolia.net/1/indexes/{INDEX}/query'

HEADERS = {
    'x-algolia-application-id': APP_ID,
    'x-algolia-api-key':        API_KEY,
    'Content-Type':             'application/json',
}

PAYLOAD = {
    'query':        '',
    'filters':      'categories:clothing',
    'hitsPerPage':  3,   # just 3 products to inspect shape
    'page':         0,
}

async def probe():
    async with aiohttp.ClientSession() as session:
        async with session.post(URL, headers=HEADERS, json=PAYLOAD) as resp:
            print(f'Status: {resp.status}')
            data = await resp.json()

    print(f"Total products in index: {data.get('nbHits')}")
    print(f"Total pages:             {data.get('nbPages')}")
    print(f"Hits per page:           {data.get('hitsPerPage')}")

    if data.get('hits'):
        print('\n=== ALL KEYS ON FIRST PRODUCT ===')
        hit = data['hits'][0]
        for k, v in hit.items():
            print(f'  {k}: {str(v)[:120]}')

        print('\n=== SAVING FULL 3-PRODUCT SAMPLE ===')
        with open('algolia_sample.json', 'w') as f:
            json.dump(data['hits'], f, indent=2)
        print('Saved to algolia_sample.json')

asyncio.run(probe())
