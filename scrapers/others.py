from models import Product
from typing import List
from urllib.parse import quote_plus
import httpx
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
}

async def _try_scrape(url: str, site: str, query: str, name_sel: str, price_sel: str, link_sel: str, rating_sel: str = None) -> List[Product]:
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(url, headers=HEADERS)
        soup = BeautifulSoup(resp.text, "html.parser")
        products = []
        containers = soup.select(name_sel)[:3] if name_sel else []
        for item in containers:
            name = item.get_text(strip=True) or query
            parent = item.find_parent("div") or item.find_parent("li") or soup
            price_el = parent.select_one(price_sel) if price_sel else None
            price_text = price_el.get_text(strip=True).replace("₹", "").replace(",", "") if price_el else ""
            match = re.search(r"([\d]+)", price_text)
            price = float(match.group(1)) if match else 0
            link_el = item.find_parent("a") or parent.select_one("a[href]")
            href = link_el["href"] if link_el and link_el.get("href") else url
            if href.startswith("/"):
                href = url.split("/search")[0].split("/?")[0] + href
            if price > 0:
                products.append(Product(name=name[:100], price=price, url=href, site=site, rating=None))
        if products:
            return products
    except Exception:
        pass
    return [Product(name=f"{site} {query}", price=0, url=url, site=site, rating=None, details=f"Could not fetch live price - click to search on {site}")]

async def scrape_myntra(query: str) -> List[Product]:
    search_url = f"https://www.myntra.com/{quote_plus(query.replace(' ', '-'))}"
    return [Product(name=f"Myntra {query}", price=0, url=search_url, site="Myntra", rating=None, details="Myntra requires browser rendering - click to search")]

async def scrape_snapdeal(query: str) -> List[Product]:
    search_url = f"https://www.snapdeal.com/search?keyword={quote_plus(query)}"
    return await _try_scrape(search_url, "Snapdeal", query, ".product-title", ".product-price", "a.dp-widget-link")

async def scrape_ajio(query: str) -> List[Product]:
    search_url = f"https://www.ajio.com/search/?text={quote_plus(query)}"
    return [Product(name=f"Ajio {query}", price=0, url=search_url, site="Ajio", rating=None, details="Ajio requires browser rendering - click to search")]

async def scrape_tatacliq(query: str) -> List[Product]:
    search_url = f"https://www.tatacliq.com/search/?searchCategory=all&text={quote_plus(query)}"
    return [Product(name=f"TataCliq {query}", price=0, url=search_url, site="TataCliq", rating=None, details="TataCliq requires browser rendering - click to search")]
