from pydantic import BaseModel
from typing import List, Optional

class Product(BaseModel):
    name: str
    price: float
    url: str
    site: str
    rating: Optional[float] = None
    details: Optional[str] = None

class ComparisonRequest(BaseModel):
    query: str
    sites: Optional[List[str]] = None

class ComparisonResult(BaseModel):
    best_product: Product
    all_products: List[Product]
    summary: str
