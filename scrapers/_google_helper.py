from models import Product
from typing import List
import httpx
from urllib.parse import quote_plus, unquote
from bs4 import BeautifulSoup
import re
import json

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
]

def _get_headers(idx=0):
    return {
        "User-Agent": _USER_AGENTS[idx % len(_USER_AGENTS)],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }

_PRICE_RE = re.compile(r"(?:₹|Rs\.?\s*|INR\s*)([\d,]+(?:\.[\d]+)?)")
_DISCOUNT_CONTEXT = re.compile(
    r"(?:discount|cut|drop|off|save|cashback|exchange|slashed)[\s\w]{0,15}?(?:₹|Rs\.?\s*|INR\s*)([\d,]+)",
    re.IGNORECASE
)


def _parse_price(text: str) -> float:
    discount_amounts = set()
    for m in _DISCOUNT_CONTEXT.findall(text):
        try:
            discount_amounts.add(float(m.replace(",", "")))
        except ValueError:
            pass

    matches = _PRICE_RE.findall(text)
    prices = []
    for m in matches:
        try:
            p = float(m.replace(",", ""))
            if 100 < p < 10_000_000 and p not in discount_amounts:
                prices.append(p)
        except ValueError:
            pass
    if not prices:
        return 0
    prices.sort()
    return prices[len(prices) // 2]


async def google_price_search(query: str, site_domain: str, site_name: str, fallback_url: str) -> List[Product]:
    """Try multiple search engines in parallel to get real product prices."""
    import asyncio

    async def _try_strategy(coro):
        try:
            return await coro
        except Exception:
            return []

    # Run all strategies in parallel — first one with results wins
    results = await asyncio.gather(
        _try_strategy(_google_search(query, site_domain, site_name, fallback_url)),
        _try_strategy(_ddg_search(query, site_domain, site_name, fallback_url)),
        _try_strategy(_bing_search(query, site_domain, site_name, fallback_url)),
        _try_strategy(_direct_scrape(query, site_domain, site_name, fallback_url)),
    )

    for products in results:
        if products:
            return products

    return [Product(
        name=f"{site_name} {query}",
        price=0,
        url=fallback_url,
        site=site_name,
        rating=None,
        details=f"Click to search on {site_name}"
    )]


async def _google_search(query: str, site_domain: str, site_name: str, fallback_url: str) -> List[Product]:
    search_query = f"{query} price site:{site_domain}"
    google_url = f"https://www.google.com/search?q={quote_plus(search_query)}&hl=en&gl=in"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=8) as client:
            resp = await client.get(google_url, headers=_get_headers(0))
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        products = []
        for result in soup.select("div.g, div[data-hveid]")[:5]:
            title_el = result.select_one("h3")
            link_el = result.select_one("a[href]")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href = link_el["href"] if link_el else fallback_url
            if href.startswith("/url?q="):
                href = href.split("/url?q=")[1].split("&")[0]
            if site_domain not in href:
                continue
            price = _parse_price(result.get_text(" ", strip=True))
            if price > 0:
                products.append(Product(name=title[:100], price=price, url=href, site=site_name, rating=None))
        if products:
            return products[:3]
    except Exception:
        pass
    return []


async def _ddg_search(query: str, site_domain: str, site_name: str, fallback_url: str) -> List[Product]:
    region = " India" if ".in" in site_domain else ""
    search_query = f"{query} price {site_name}{region}"
    ddg_url = f"https://html.duckduckgo.com/html/?q={quote_plus(search_query)}"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=8) as client:
            resp = await client.get(ddg_url, headers=_get_headers(1))
        if resp.status_code != 200 or not resp.text[:20].isprintable():
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        products = []
        site_lower = site_name.lower()
        for result in soup.select(".result, .web-result")[:8]:
            title_el = result.select_one(".result__a, .result__title a")
            snippet_el = result.select_one(".result__snippet")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href = title_el.get("href", fallback_url)
            if "uddg=" in href:
                href = unquote(href.split("uddg=")[1].split("&")[0])
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            all_text = title + " " + snippet
            if site_lower not in all_text.lower() and site_domain not in href:
                continue
            price = _parse_price(all_text)
            if price > 0:
                product_url = href if site_domain in href else fallback_url
                products.append(Product(name=title[:100], price=price, url=product_url, site=site_name, rating=None))
        if products:
            return products[:3]
    except Exception:
        pass
    return []


async def _bing_search(query: str, site_domain: str, site_name: str, fallback_url: str) -> List[Product]:
    """Bing often works from cloud IPs when Google/DDG block."""
    search_query = f"{query} price site:{site_domain}"
    bing_url = f"https://www.bing.com/search?q={quote_plus(search_query)}&setlang=en&cc=IN"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=8) as client:
            resp = await client.get(bing_url, headers=_get_headers(2))
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        products = []
        for result in soup.select("li.b_algo, .b_algo")[:5]:
            title_el = result.select_one("h2 a, h2")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            if not href or site_domain not in href:
                continue
            all_text = result.get_text(" ", strip=True)
            price = _parse_price(all_text)
            if price > 0:
                products.append(Product(name=title[:100], price=price, url=href, site=site_name, rating=None))

        # Also try Bing without site: — search for price mentions
        if not products:
            search_query2 = f"{query} price {site_name} India"
            bing_url2 = f"https://www.bing.com/search?q={quote_plus(search_query2)}&setlang=en&cc=IN"
            async with httpx.AsyncClient(follow_redirects=True, timeout=8) as client:
                resp2 = await client.get(bing_url2, headers=_get_headers(0))
            if resp2.status_code == 200:
                soup2 = BeautifulSoup(resp2.text, "html.parser")
                site_lower = site_name.lower()
                for result in soup2.select("li.b_algo, .b_algo")[:6]:
                    title_el = result.select_one("h2 a, h2")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    href = title_el.get("href", "")
                    snippet = result.get_text(" ", strip=True)
                    if site_lower not in (title + " " + snippet).lower() and site_domain not in href:
                        continue
                    price = _parse_price(snippet)
                    if price > 0:
                        product_url = href if site_domain in href else fallback_url
                        products.append(Product(name=title[:100], price=price, url=product_url, site=site_name, rating=None))

        if products:
            return products[:3]
    except Exception:
        pass
    return []


async def _direct_scrape(query: str, site_domain: str, site_name: str, fallback_url: str) -> List[Product]:
    """Direct scraping with JSON-LD, meta tags, and text extraction."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=8) as client:
            resp = await client.get(fallback_url, headers=_get_headers(0))
        if resp.status_code >= 400:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")

        # Try JSON-LD structured data
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string or "")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict) and "offers" in item:
                        offers = item["offers"]
                        if isinstance(offers, dict):
                            offers = [offers]
                        if isinstance(offers, list):
                            for o in offers[:3]:
                                p = float(o.get("price", 0))
                                name = item.get("name", f"{site_name} {query}")
                                url = o.get("url", fallback_url)
                                if p > 100:
                                    return [Product(name=name[:100], price=p, url=url or fallback_url, site=site_name, rating=None)]
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        # Try meta tags
        meta_price = soup.select_one('meta[property="product:price:amount"], meta[property="og:price:amount"]')
        if meta_price and meta_price.get("content"):
            try:
                p = float(meta_price["content"].replace(",", ""))
                if p > 100:
                    return [Product(name=f"{site_name} {query}", price=p, url=fallback_url, site=site_name, rating=None, details="Price from product page")]
            except ValueError:
                pass

        # Regex extraction from full page text
        all_text = soup.get_text(" ", strip=True)
        price = _parse_price(all_text)
        if price > 0:
            return [Product(name=f"{site_name} {query}", price=price, url=fallback_url, site=site_name, rating=None, details="Estimated price from search")]
    except Exception:
        pass
    return []
