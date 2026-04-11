# run.py
# Entry point for the Stacia's Closet scraper.
#
# Usage:
#   python run.py                    — run on schedule
#   python run.py --once             — run once and exit
#   python run.py --site abercrombie — scrape one site only, then exit
#   python run.py --skip-abercrombie — skip A&F (used in GitHub Actions)

import asyncio
import argparse
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import SITES, REFRESH_INTERVAL_SECONDS, HEAVY_SITE_CYCLE_INTERVAL
from scraper import scrape_all
from db import init_db, upsert_products, product_count, export_json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

_cycle_count = 0


# ---------------------------------------------------------------------------
# Core scrape cycle
# ---------------------------------------------------------------------------

def _sites_for_cycle(cycle: int) -> dict:
    selected = {}
    for key, cfg in SITES.items():
        if key == "wayward":
            selected[key] = cfg
        elif key != "abercrombie" and cycle % HEAVY_SITE_CYCLE_INTERVAL == 0:
            selected[key] = cfg
    return selected


async def run_scrape(site_key: str | None = None, all_sites: bool = False) -> None:
    global _cycle_count
    _cycle_count += 1

    if site_key:
        if site_key not in SITES:
            logger.error(f"Unknown site key: {site_key}. Options: {list(SITES.keys())}")
            return
        sites = {site_key: SITES[site_key]}
    elif all_sites:
        sites = SITES
    else:
        sites = _sites_for_cycle(_cycle_count)

    site_names = [SITES[k]["name"] for k in sites]
    logger.info(f"=== Scrape cycle {_cycle_count} — sites: {', '.join(site_names)} ===")

    # Step 1: scrape all sites in scope
    products = await scrape_all(sites)

    if products:
        saved = upsert_products(products)
        logger.info(f"Saved/updated {saved} products. DB total: {product_count()}")
    else:
        logger.warning("No products returned this cycle.")

    # Step 2: export clean JSON — exclude A&F unless this was an explicit A&F scrape
    _exclude = None if site_key == "abercrombie" else ["abercrombie"]
    exported = export_json(exclude_sites=_exclude)
    logger.info(f"Exported {exported} products to docs/products.json")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(description="Stacia's Closet scraper")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--site", type=str, default=None,
                        help="Scrape one site only (wayward | aritzia | abercrombie)")
    parser.add_argument("--skip-abercrombie", action="store_true",
                        help="Skip Abercrombie (useful in CI)")
    args = parser.parse_args()

    init_db()
    logger.info(f"DB initialised. Current product count: {product_count()}")

    if args.once or args.site:
        if args.skip_abercrombie and not args.site:
            filtered_sites = {k: v for k, v in SITES.items() if k != 'abercrombie'}
            import config as _cfg
            _original = _cfg.SITES.copy()
            _cfg.SITES = filtered_sites
            await run_scrape(args.site)
            _cfg.SITES = _original
        else:
            # --once with no specific site runs all 3
            await run_scrape(args.site, all_sites=not args.site)
        return

    # Scheduled mode
    logger.info(f"Scheduler starting. Refresh every {REFRESH_INTERVAL_SECONDS // 60} minutes.")
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_scrape, "interval", seconds=REFRESH_INTERVAL_SECONDS, id="scrape_job")
    scheduler.start()
    await run_scrape()

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down scheduler.")
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
