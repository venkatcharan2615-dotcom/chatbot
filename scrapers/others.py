from models import Product
from typing import List

async def scrape_myntra(query: str) -> List[Product]:
    # Placeholder: Replace with real scraping logic or Myntra API
    return [Product(name=f"Myntra {query}", price=970.0, url="https://myntra.com/dummy", site="Myntra", rating=4.1)]

async def scrape_snapdeal(query: str) -> List[Product]:
    # Placeholder: Replace with real scraping logic or Snapdeal API
    return [Product(name=f"Snapdeal {query}", price=960.0, url="https://snapdeal.com/dummy", site="Snapdeal", rating=3.9)]

async def scrape_ajio(query: str) -> List[Product]:
    # Placeholder: Replace with real scraping logic or Ajio API
    return [Product(name=f"Ajio {query}", price=980.0, url="https://ajio.com/dummy", site="Ajio", rating=4.0)]

async def scrape_tatacliq(query: str) -> List[Product]:
    # Placeholder: Replace with real scraping logic or TataCliq API
    return [Product(name=f"TataCliq {query}", price=965.0, url="https://tatacliq.com/dummy", site="TataCliq", rating=4.2)]
