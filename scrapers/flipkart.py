from models import Product
from typing import List
import httpx
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
}

async def scrape_flipkart(query: str) -> List[Product]:
    search_url = f"https://www.flipkart.com/search?q={quote_plus(query)}"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(search_url, headers=HEADERS)
        soup = BeautifulSoup(resp.text, "html.parser")
        products = []
        for item in soup.select('[data-id]')[:3]:
            name_el = item.select_one('a[title]') or item.select_one('[class*="title"] a') or item.select_one('a[class*="wjcEIp"]')
            price_el = item.select_one('[class*="Nx9bqj"]') or item.select_one('[class*="price"]') or item.select_one('div._30jeq3')
            link_el = item.select_one('a[href*="/p/"]') or item.select_one('a[title]')
            rating_el = item.select_one('[class*="XQDdHH"]') or item.select_one('div._3LWZlK')
            if not price_el:
                continue
            name = name_el.get("title", "") or name_el.get_text(strip=True) if name_el else query
            price_text = price_el.get_text(strip=True).replace("₹", "").replace(",", "").strip()
            match = re.search(r"([\d]+)", price_text)
            price = float(match.group(1)) if match else 0
            url = "https://www.flipkart.com" + link_el["href"] if link_el and link_el.get("href", "").startswith("/") else search_url
            rating = None
            if rating_el:
                rmatch = re.search(r"([\d.]+)", rating_el.get_text())
                if rmatch:
                    rating = float(rmatch.group(1))
            if price > 0:
                products.append(Product(name=name[:100], price=price, url=url, site="Flipkart", rating=rating))
        if products:
            return products
    except Exception:
        pass
    return [Product(name=f"Flipkart {query}", price=0, url=search_url, site="Flipkart", rating=None, details="Could not fetch live price - click to search on Flipkart")]
