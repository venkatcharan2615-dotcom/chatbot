from models import Product
from typing import List
import httpx
from urllib.parse import quote_plus

async def scrape_flipkart(query: str) -> List[Product]:
    search_url = f"https://www.flipkart.com/search?q={quote_plus(query)}"
    return [Product(name=f"Flipkart {query}", price=950.0, url=search_url, site="Flipkart", rating=4.0)]
