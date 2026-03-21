from models import Product
from typing import List
from scrapers._google_helper import google_price_search
from urllib.parse import quote_plus

async def scrape_flipkart(query: str) -> List[Product]:
    search_url = f"https://www.flipkart.com/search?q={quote_plus(query)}"
    return await google_price_search(query, "flipkart.com", "Flipkart", search_url)
