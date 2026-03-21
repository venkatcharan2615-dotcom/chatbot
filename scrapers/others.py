from models import Product
from typing import List
from scrapers._google_helper import google_price_search
from urllib.parse import quote_plus


async def scrape_myntra(query: str) -> List[Product]:
    search_url = f"https://www.myntra.com/{quote_plus(query.replace(' ', '-'))}"
    return await google_price_search(query, "myntra.com", "Myntra", search_url)

async def scrape_snapdeal(query: str) -> List[Product]:
    search_url = f"https://www.snapdeal.com/search?keyword={quote_plus(query)}"
    return await google_price_search(query, "snapdeal.com", "Snapdeal", search_url)

async def scrape_ajio(query: str) -> List[Product]:
    search_url = f"https://www.ajio.com/search/?text={quote_plus(query)}"
    return await google_price_search(query, "ajio.com", "Ajio", search_url)

async def scrape_tatacliq(query: str) -> List[Product]:
    search_url = f"https://www.tatacliq.com/search/?searchCategory=all&text={quote_plus(query)}"
    return await google_price_search(query, "tatacliq.com", "TataCliq", search_url)

async def scrape_zepto(query: str) -> List[Product]:
    search_url = f"https://www.zeptonow.com/search?query={quote_plus(query)}"
    return await google_price_search(query, "zeptonow.com", "Zepto", search_url)

async def scrape_zomato(query: str) -> List[Product]:
    search_url = f"https://www.zomato.com/search?q={quote_plus(query)}"
    return await google_price_search(query, "zomato.com", "Zomato", search_url)

async def scrape_instamart(query: str) -> List[Product]:
    search_url = f"https://www.swiggy.com/instamart/search?query={quote_plus(query)}"
    return await google_price_search(query, "swiggy.com", "Instamart", search_url)
