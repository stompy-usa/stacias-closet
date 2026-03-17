import asyncio
from playwright.async_api import async_playwright

async def compare():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        )

        for slug in ['womens-new-arrivals', 'womens-tops']:
            page = await context.new_page()
            print(f'\n=== {slug} ===')
            await page.goto(f'https://www.abercrombie.com/shop/us/{slug}',
                            timeout=30000, wait_until='domcontentloaded')
            await page.wait_for_timeout(8000)

            summary = await page.evaluate('''() => {
                const bodyText = document.body.innerText.slice(0, 800);
                return {
                    productLinks:   document.querySelectorAll("a[href*='/shop/us/p/']").length,
                    allLinks:       document.querySelectorAll("a[href]").length,
                    images:         document.querySelectorAll("img").length,
                    // Look for any grid/list container
                    gridEls:        document.querySelectorAll("[class*=grid], [class*=Grid]").length,
                    // Check for any error or loading indicators
                    bodyPreview:    bodyText,
                    // What's the main content area look like?
                    mainContent:    document.querySelector("main")?.className || "no main",
                    // Any data-* attributes that hint at products
                    dataProductEls: document.querySelectorAll("[data-product-id], [data-product-name]").length,
                    // Check for pagination which would mean products loaded
                    pagination:     document.querySelectorAll("[class*=pagination], [class*=Pagination]").length,
                    // Check for "no results" type messaging
                    pageHTML:       document.documentElement.innerHTML.slice(0, 200),
                };
            }''')

            print(f'Product links:    {summary["productLinks"]}')
            print(f'All links:        {summary["allLinks"]}')
            print(f'Images:           {summary["images"]}')
            print(f'Grid elements:    {summary["gridEls"]}')
            print(f'Data-product els: {summary["dataProductEls"]}')
            print(f'Pagination:       {summary["pagination"]}')
            print(f'Main class:       {summary["mainContent"]}')
            print(f'Body preview:\n{summary["bodyPreview"][:400]}')
            await page.close()

        await context.close()

asyncio.run(compare())
