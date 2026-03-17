# db.py
# SQLite cache for scraped products.
# Products are upserted by (site, product_url) so re-scraping updates
# existing rows rather than creating duplicates.

import sqlite3
import os
from datetime import datetime, timezone
from config import DB_PATH


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the products table if it doesn't exist."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                site         TEXT    NOT NULL,
                name         TEXT    NOT NULL,
                price        TEXT,
                image_url    TEXT,
                product_url  TEXT    NOT NULL,
                category     TEXT,
                scraped_at   TEXT    NOT NULL,
                UNIQUE(site, product_url)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_site ON products(site)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON products(category)")
        conn.commit()


def upsert_products(products: list[dict]) -> int:
    """
    Insert or update a list of product dicts.
    Returns the number of rows affected.
    """
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        (
            p["site"],
            p["name"],
            p.get("price", "N/A"),
            p.get("image_url", ""),
            p["product_url"],
            p.get("category", "Other"),
            now,
        )
        for p in products
    ]
    with _connect() as conn:
        cursor = conn.executemany("""
            INSERT INTO products (site, name, price, image_url, product_url, category, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(site, product_url) DO UPDATE SET
                name       = excluded.name,
                price      = excluded.price,
                image_url  = excluded.image_url,
                category   = excluded.category,
                scraped_at = excluded.scraped_at
        """, rows)
        conn.commit()
        return cursor.rowcount


def get_products(site: str | None = None, category: str | None = None) -> list[dict]:
    """
    Fetch products from the DB, optionally filtered by site and/or category.
    Returns a list of plain dicts sorted by scraped_at descending.
    """
    query = "SELECT * FROM products WHERE 1=1"
    params: list = []
    if site:
        query += " AND site = ?"
        params.append(site)
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY scraped_at DESC"

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_sites() -> list[str]:
    """Return list of distinct site keys currently in the DB."""
    with _connect() as conn:
        rows = conn.execute("SELECT DISTINCT site FROM products").fetchall()
    return [r["site"] for r in rows]


def get_categories() -> list[str]:
    """Return list of distinct categories currently in the DB."""
    with _connect() as conn:
        rows = conn.execute("SELECT DISTINCT category FROM products ORDER BY category").fetchall()
    return [r["category"] for r in rows]


def product_count() -> int:
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) as c FROM products").fetchone()
    return row["c"]


def export_json(path: str = "docs/products.json") -> int:
    """
    Export all products to a static JSON file for GitHub Pages.
    Returns the number of products exported.
    """
    import json, os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    products = get_products()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False)
    return len(products)
