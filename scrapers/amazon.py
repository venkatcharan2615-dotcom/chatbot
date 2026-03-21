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

async def scrape_amazon(query: str) -> List[Product]:
    search_url = f"https://www.amazon.in/s?k={quote_plus(query)}"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(search_url, headers=HEADERS)
        soup = BeautifulSoup(resp.text, "html.parser")
        products = []
        for item in soup.select('[data-component-type="s-search-result"]')[:3]:
            name_el = item.select_one("h2 a span")
            price_el = item.select_one(".a-price-whole")
            link_el = item.select_one("h2 a")
            rating_el = item.select_one(".a-icon-alt")
            if not name_el or not price_el:
                continue
            name = name_el.get_text(strip=True)
            price_text = price_el.get_text(strip=True).replace(",", "").replace(".", "")
            price = float(price_text) if price_text.isdigit() else 0
            url = "https://www.amazon.in" + link_el["href"] if link_el else search_url
            rating = None
            if rating_el:
                match = re.search(r"([\d.]+)", rating_el.get_text())
                if match:
                    rating = float(match.group(1))
            if price > 0:
                products.append(Product(name=name[:100], price=price, url=url, site="Amazon", rating=rating))
        if products:
            return products
    except Exception:
        pass
    return [Product(name=f"Amazon {query}", price=0, url=search_url, site="Amazon", rating=None, details="Could not fetch live price - click to search on Amazon")]
