from models import Product
from typing import List
import httpx
from urllib.parse import quote_plus

async def scrape_amazon(query: str) -> List[Product]:
    search_url = f"https://www.amazon.in/s?k={quote_plus(query)}"
    return [Product(name=f"Amazon {query}", price=999.0, url=search_url, site="Amazon", rating=4.2)]
