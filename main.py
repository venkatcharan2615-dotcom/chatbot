from fastapi import FastAPI, HTTPException
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
