# api.py
# Lightweight Flask API — serves product data from SQLite to the lookbook frontend.
#
# Endpoints:
#   GET /api/products              — all products (optional ?site= ?category= filters)
#   GET /api/filters               — available sites + categories for filter UI
#   GET /api/stats                 — product count + last scraped timestamp
#
# Run:
#   pip install flask flask-cors
#   python api.py

from flask import Flask, jsonify, request
from flask_cors import CORS
from db import get_products, get_sites, get_categories, product_count, _connect

app = Flask(__name__)
CORS(app)  # allow the lookbook HTML to fetch from localhost


@app.route("/api/products")
def products():
    site     = request.args.get("site")
    category = request.args.get("category")
    data     = get_products(site=site, category=category)
    return jsonify(data)


@app.route("/api/filters")
def filters():
    return jsonify({
        "sites":      get_sites(),
        "categories": get_categories(),
    })


@app.route("/api/stats")
def stats():
    with _connect() as conn:
        row = conn.execute(
            "SELECT MAX(scraped_at) as last_scraped FROM products"
        ).fetchone()
    return jsonify({
        "total_products": product_count(),
        "last_scraped":   row["last_scraped"] if row else None,
    })


if __name__ == "__main__":
    app.run(port=5050, debug=True)
