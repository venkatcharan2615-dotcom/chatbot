from models import Product
from typing import List
from urllib.parse import quote_plus

async def scrape_myntra(query: str) -> List[Product]:
    search_url = f"https://www.myntra.com/{quote_plus(query.replace(' ', '-'))}"
    return [Product(name=f"Myntra {query}", price=970.0, url=search_url, site="Myntra", rating=4.1)]

async def scrape_snapdeal(query: str) -> List[Product]:
    search_url = f"https://www.snapdeal.com/search?keyword={quote_plus(query)}"
    return [Product(name=f"Snapdeal {query}", price=960.0, url=search_url, site="Snapdeal", rating=3.9)]

async def scrape_ajio(query: str) -> List[Product]:
    search_url = f"https://www.ajio.com/search/?text={quote_plus(query)}"
    return [Product(name=f"Ajio {query}", price=980.0, url=search_url, site="Ajio", rating=4.0)]

async def scrape_tatacliq(query: str) -> List[Product]:
    search_url = f"https://www.tatacliq.com/search/?searchCategory=all&text={quote_plus(query)}"
    return [Product(name=f"TataCliq {query}", price=965.0, url=search_url, site="TataCliq", rating=4.2)]
