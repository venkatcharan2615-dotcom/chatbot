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

# Accessory keywords to filter out from results
_ACCESSORY_WORDS = re.compile(
    r"\b(case|cover|pouch|sleeve|skin|protector|tempered\s*glass|screen\s*guard|"
    r"charger|cable|adapter|holder|stand|mount|strap|band|loop|sticker|decal|"
    r"back\s*cover|flip\s*cover|bumper|armor|wallet\s*case)\b",
    re.IGNORECASE
)

# Product type detection for smarter search queries
_PHONE_BRANDS = {"iphone", "samsung", "pixel", "oneplus", "redmi", "realme", "poco",
                 "vivo", "oppo", "motorola", "moto", "nothing", "iqoo", "galaxy"}
_LAPTOP_WORDS = {"laptop", "macbook", "chromebook", "notebook"}
_WATCH_WORDS = {"watch", "smartwatch", "band"}
_TV_WORDS = {"tv", "television"}
_TABLET_WORDS = {"ipad", "tablet"}


def _refine_query(query: str) -> str:
    """Add product type to query for more accurate results."""
    q_lower = query.lower()
    words = set(q_lower.split())

    # Already has a type word — don't add
    type_words = {"phone", "mobile", "smartphone", "laptop", "watch", "smartwatch",
                  "tv", "television", "tablet", "earbuds", "headphone", "speaker",
                  "case", "cover", "charger"}
    if words & type_words:
        return query

    if words & _PHONE_BRANDS:
        return query + " smartphone"
    if words & _LAPTOP_WORDS:
        return query + " laptop"
    if words & _WATCH_WORDS:
        return query + " smartwatch"
    if words & _TV_WORDS:
        return query + " television"
    if words & _TABLET_WORDS:
        return query + " tablet"
    return query


def _is_accessory(title: str) -> bool:
    """Check if a product title is an accessory (case, cover, etc.)."""
    return bool(_ACCESSORY_WORDS.search(title))


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
    """Try multiple search strategies in parallel to get real product prices."""
    import asyncio

    refined = _refine_query(query)

    async def _try_strategy(coro):
        try:
            return await coro
        except Exception:
            return []

    # Brave Search works best from cloud IPs, DDG Lite as backup, plus direct scrape
    results = await asyncio.gather(
        _try_strategy(_brave_search(refined, site_domain, site_name, fallback_url)),
        _try_strategy(_ddg_lite_search(refined, site_domain, site_name, fallback_url)),
        _try_strategy(_direct_scrape(query, site_domain, site_name, fallback_url)),
        _try_strategy(_bing_search(refined, site_domain, site_name, fallback_url)),
    )

    for products in results:
        # Filter out accessories
        filtered = [p for p in products if not _is_accessory(p.name)]
        if filtered:
            return filtered
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


async def brave_web_search(query: str) -> str:
    """Search the web via Brave and return text snippets for AI grounding."""
    url = "https://search.brave.com/search"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            resp = await client.get(url, params={"q": query, "country": "in"}, headers={
                "User-Agent": _USER_AGENTS[0],
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-IN,en;q=0.9",
            })
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        snippets = []
        for r in soup.select("#results .snippet, [data-type='web']")[:6]:
            title_el = r.select_one(".snippet-title, .title, h2, a")
            desc_el = r.select_one(".snippet-description, .snippet-content, .description")
            title = title_el.get_text(strip=True) if title_el else ""
            desc = desc_el.get_text(strip=True) if desc_el else ""
            if title:
                snippets.append(f"- {title}: {desc}" if desc else f"- {title}")
        return "\n".join(snippets[:5])
    except Exception:
        return ""


def _clean_brave_title(title: str, site_name: str) -> str:
    """Strip Brave's site-name prefix from titles like 'Flipkartflipkart.com› home › ...'."""
    # Remove site prefix patterns like "Flipkartflipkart.com› path › ..."
    title = re.sub(r'^[A-Za-z]+[a-z]+\.(?:com|in|org)[›\s]+(?:[^›]+[›\s]+)*', '', title).strip()
    # Remove YouTube duration prefix like "05:47YouTube"
    title = re.sub(r'^\d{2}:\d{2}YouTube', '', title).strip()
    # Remove leading site names
    for prefix in [site_name, "Times of India", "YouTube", "My Mobile India"]:
        if title.startswith(prefix):
            title = title[len(prefix):].strip()
    # Clean breadcrumb separators
    title = re.sub(r'^[›\-\|:]+\s*', '', title).strip()
    return title if title else f"{site_name} product"


async def _brave_search(query: str, site_domain: str, site_name: str, fallback_url: str) -> List[Product]:
    """Brave Search — works reliably from cloud IPs."""
    search_query = f"{query} price {site_name} India"
    url = "https://search.brave.com/search"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            resp = await client.get(url, params={"q": search_query, "country": "in"}, headers={
                "User-Agent": _USER_AGENTS[0],
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-IN,en;q=0.9",
            })
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        products = []
        site_lower = site_name.lower()

        for r in soup.select("#results .snippet, [data-type='web']")[:10]:
            title_el = r.select_one(".snippet-title, .title, h2 a, a")
            desc_el = r.select_one(".snippet-description, .snippet-content, .description")
            url_el = r.select_one("a[href^='http']")

            title = title_el.get_text(strip=True) if title_el else ""
            desc = desc_el.get_text(strip=True) if desc_el else ""
            href = url_el.get("href", "") if url_el else ""
            all_text = title + " " + desc

            # Must relate to our target site
            if site_lower not in all_text.lower() and site_domain not in href:
                continue

            price = _parse_price(all_text)
            if price > 0:
                product_url = href if site_domain in href else fallback_url
                clean_title = _clean_brave_title(title, site_name) if title else f"{site_name} {query}"
                products.append(Product(
                    name=clean_title[:100],
                    price=price, url=product_url, site=site_name, rating=None
                ))

        if products:
            return products[:3]
    except Exception:
        pass
    return []


async def _ddg_lite_search(query: str, site_domain: str, site_name: str, fallback_url: str) -> List[Product]:
    """DuckDuckGo Lite — lightweight, works from cloud IPs."""
    search_query = f"{query} price {site_name} India"
    url = "https://lite.duckduckgo.com/lite/"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            resp = await client.post(url, data={"q": search_query}, headers={
                "User-Agent": _USER_AGENTS[1],
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/html",
            })
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        products = []
        site_lower = site_name.lower()

        # DDG Lite uses table rows with result links and snippet text
        rows = soup.select("table")
        for table in rows:
            for link in table.select("a.result-link, td a[href^='http']"):
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if "duckduckgo.com" in href:
                    continue
                # Get surrounding text for price
                parent_row = link.find_parent("tr")
                snippet = ""
                if parent_row:
                    next_rows = parent_row.find_next_siblings("tr", limit=2)
                    for nr in next_rows:
                        snippet += " " + nr.get_text(strip=True)

                all_text = title + " " + snippet
                if site_lower not in all_text.lower() and site_domain not in href:
                    continue

                price = _parse_price(all_text)
                if price > 0:
                    product_url = href if site_domain in href else fallback_url
                    products.append(Product(
                        name=title[:100] if title else f"{site_name} {query}",
                        price=price, url=product_url, site=site_name, rating=None
                    ))

        if products:
            return products[:3]
    except Exception:
        pass
    return []


async def _bing_search(query: str, site_domain: str, site_name: str, fallback_url: str) -> List[Product]:
    """Bing as fallback."""
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
