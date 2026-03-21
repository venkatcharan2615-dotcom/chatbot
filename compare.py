from models import Product
from typing import List

def compare_products(products: List[Product]) -> Product:
    # Simple logic: choose lowest price
    return min(products, key=lambda p: p.price)
