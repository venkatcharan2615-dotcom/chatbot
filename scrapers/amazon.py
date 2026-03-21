from models import Product
from typing import List
import httpx
from bs4 import BeautifulSoup

async def scrape_amazon(query: str) -> List[Product]:
    # Placeholder: Replace with real scraping logic or Amazon API
    return [Product(name=f"Amazon {query}", price=999.0, url="https://amazon.in/dummy", site="Amazon", rating=4.2)]
