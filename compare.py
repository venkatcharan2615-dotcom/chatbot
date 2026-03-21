from models import Product
from typing import List

def compare_products(products: List[Product]) -> Product:
    priced = [p for p in products if p.price > 0]
    if priced:
        return min(priced, key=lambda p: p.price)
    return products[0]
