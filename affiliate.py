import os
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# Affiliate IDs — set these as environment variables on Render
# Amazon Associates: sign up at https://affiliate-program.amazon.in
# Flipkart Affiliate: sign up at https://affiliate.flipkart.com
_AFFILIATE_TAGS = {
    "amazon": {"param": "tag", "id": os.getenv("AMAZON_AFFILIATE_TAG", "allada-21")},
    "flipkart": {"param": "affid", "id": os.getenv("FLIPKART_AFFILIATE_ID", "")},
}


def add_affiliate_tag(url: str, site: str) -> str:
    """Append affiliate tracking parameter to a product URL."""
    config = _AFFILIATE_TAGS.get(site.lower())
    if not config or not config["id"]:
        return url
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        params[config["param"]] = [config["id"]]
        new_query = urlencode(params, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
    except Exception:
        return url


def tag_products(products) -> None:
    """Add affiliate tags to all products in-place."""
    for p in products:
        if p.url:
            p.url = add_affiliate_tag(p.url, p.site)
