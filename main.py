from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from models import ComparisonRequest, ComparisonResult, Product
from scrapers.amazon import scrape_amazon
from scrapers.flipkart import scrape_flipkart
from scrapers.others import (
    scrape_myntra, scrape_snapdeal, scrape_ajio, scrape_tatacliq
)
from compare import compare_products
from llm.openai_llm import summarize_products
import asyncio

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Product Comparison Chatbot</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; display: flex; flex-direction: column; align-items: center; padding: 2rem; }
        h1 { color: #38bdf8; margin-bottom: 0.5rem; }
        .subtitle { color: #94a3b8; margin-bottom: 2rem; }
        .search-box { display: flex; gap: 0.5rem; margin-bottom: 2rem; width: 100%; max-width: 600px; }
        input { flex: 1; padding: 0.75rem 1rem; border-radius: 8px; border: 1px solid #334155; background: #1e293b; color: #e2e8f0; font-size: 1rem; }
        input:focus { outline: none; border-color: #38bdf8; }
        button { padding: 0.75rem 1.5rem; border-radius: 8px; border: none; background: #2563eb; color: white; font-size: 1rem; cursor: pointer; }
        button:hover { background: #1d4ed8; }
        button:disabled { background: #475569; cursor: not-allowed; }
        .loading { display: none; color: #38bdf8; margin: 1rem; }
        .results { width: 100%; max-width: 900px; }
        .summary { background: #1e293b; padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem; border-left: 4px solid #38bdf8; }
        .best-badge { display: inline-block; background: #16a34a; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-left: 0.5rem; }
        .product-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 1rem; }
        .product-card { background: #1e293b; border-radius: 8px; padding: 1rem; border: 1px solid #334155; }
        .product-card.best { border-color: #16a34a; }
        .product-name { font-weight: 600; color: #f1f5f9; margin-bottom: 0.5rem; }
        .product-price { color: #4ade80; font-size: 1.25rem; font-weight: 700; }
        .product-site { color: #94a3b8; font-size: 0.875rem; }
        .product-rating { color: #fbbf24; }
        .error { background: #7f1d1d; padding: 1rem; border-radius: 8px; margin: 1rem 0; }
    </style>
</head>
<body>
    <h1>Product Comparison Chatbot</h1>
    <p class="subtitle">Compare prices across Amazon, Flipkart, Myntra, Snapdeal, Ajio & TataCliq</p>
    <div class="search-box">
        <input type="text" id="query" placeholder="Search for a product (e.g., laptop, headphones)" onkeypress="if(event.key==='Enter')search()">
        <button id="searchBtn" onclick="search()">Compare</button>
    </div>
    <div class="loading" id="loading">Searching across all sites...</div>
    <div class="results" id="results"></div>
    <script>
        async function search() {
            const query = document.getElementById('query').value.trim();
            if (!query) return;
            const btn = document.getElementById('searchBtn');
            const loading = document.getElementById('loading');
            const results = document.getElementById('results');
            btn.disabled = true;
            loading.style.display = 'block';
            results.innerHTML = '';
            try {
                const res = await fetch('/chatbot/compare', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({query: query})
                });
                if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Request failed'); }
                const data = await res.json();
                let html = '<div class="summary"><strong>Summary:</strong> ' + data.summary + '</div>';
                html += '<div class="product-grid">';
                data.all_products.forEach(p => {
                    const isBest = p.name === data.best_product.name && p.site === data.best_product.site;
                    html += '<div class="product-card ' + (isBest ? 'best' : '') + '">';
                    html += '<div class="product-name">' + p.name + (isBest ? '<span class="best-badge">BEST DEAL</span>' : '') + '</div>';
                    html += '<div class="product-price">&#8377;' + p.price + '</div>';
                    html += '<div class="product-site">' + p.site + '</div>';
                    html += '<div class="product-rating">' + (p.rating ? '&#9733; ' + p.rating : '') + '</div>';
                    html += '</div>';
                });
                html += '</div>';
                results.innerHTML = html;
            } catch(e) {
                results.innerHTML = '<div class="error">' + e.message + '</div>';
            }
            btn.disabled = false;
            loading.style.display = 'none';
        }
    </script>
</body>
</html>
"""

SCRAPER_MAP = {
    "amazon": scrape_amazon,
    "flipkart": scrape_flipkart,
    "myntra": scrape_myntra,
    "snapdeal": scrape_snapdeal,
    "ajio": scrape_ajio,
    "tatacliq": scrape_tatacliq,
}

@app.post("/chatbot/compare", response_model=ComparisonResult)
async def compare_endpoint(request: ComparisonRequest):
    try:
        sites = request.sites or list(SCRAPER_MAP.keys())
        tasks = [SCRAPER_MAP[site](request.query) for site in sites if site in SCRAPER_MAP]
        if not tasks:
            raise HTTPException(status_code=400, detail="No valid e-commerce sites specified.")
        results = await asyncio.gather(*tasks)
        all_products = [p for sublist in results for p in sublist]
        if not all_products:
            raise HTTPException(status_code=404, detail="No products found.")
        best = compare_products(all_products)
        summary = summarize_products(all_products)
        return ComparisonResult(best_product=best, all_products=all_products, summary=summary)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
