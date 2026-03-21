from models import Product
from typing import List
from scrapers._google_helper import google_price_search
from urllib.parse import quote_plus

async def scrape_amazon(query: str) -> List[Product]:
    search_url = f"https://www.amazon.in/s?k={quote_plus(query)}"
    products = await google_price_search(query, "amazon.in", "Amazon", search_url)
    return products
