import asyncio
import json
from playwright.async_api import async_playwright

async def diagnose():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'sec-ch-ua': '"Chromium";v="122", "Not(A:Brand";v="24"',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'none',
            }
        )
        page = await context.new_page()

        try:
            await page.goto('https://www.abercrombie.com/shop/us/womens-new-arrivals',
                            timeout=30000, wait_until='domcontentloaded')
            await page.wait_for_timeout(5000)

            # Scroll down to trigger lazy loading
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
            await page.wait_for_timeout(3000)
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.wait_for_timeout(3000)

            # Save full HTML
            html = await page.content()
            with open('abercrombie_rendered.html', 'w', encoding='utf-8') as f:
                f.write(html)
            print(f'HTML saved: {len(html)} chars')

            # Check what's actually in the DOM
            title   = await page.title()
            summary = await page.evaluate('''() => {
                return {
                    title:       document.title,
                    bodyText:    document.body.innerText.slice(0, 500),
                    allAnchors:  Array.from(document.querySelectorAll("a[href*='/shop/us/p/']")).length,
                    allImgs:     Array.from(document.querySelectorAll("img[src*='img.abercrombie.com']")).length,
                    bodyClasses: document.body.className,
                    // Check for bot/block indicators
                    isBlocked:   document.body.innerText.includes("access denied") ||
                                 document.body.innerText.toLowerCase().includes("robot") ||
                                 document.body.innerText.toLowerCase().includes("captcha"),
                    // Count meaningful elements
                    productLinks: Array.from(document.querySelectorAll("a[href*='/shop/us/p/']"))
                                      .slice(0, 5)
                                      .map(a => ({href: a.href, text: a.textContent.trim().slice(0,40)})),
                    // All unique class names containing 'product'
                    productClasses: [...new Set(
                        Array.from(document.querySelectorAll("[class*='product']"))
                             .map(el => el.className.toString().slice(0, 80))
                    )].slice(0, 10),
                };
            }''')

            print(f'\nPage title: {title}')
            print(f'Product links (a[href*/shop/us/p/]): {summary["allAnchors"]}')
            print(f'Abercrombie images: {summary["allImgs"]}')
            print(f'Is blocked: {summary["isBlocked"]}')
            print(f'\nProduct link samples:')
            for l in summary['productLinks']:
                print(f'  {l}')
            print(f'\nProduct-related classes in DOM:')
            for c in summary['productClasses']:
                print(f'  {c}')
            print(f'\nBody text preview:\n{summary["bodyText"]}')

        except Exception as e:
            print(f'Error: {e}')
        finally:
            await browser.close()

asyncio.run(diagnose())
