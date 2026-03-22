from models import Product
from typing import List, Dict, Set
import httpx
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import re
import json
import asyncio

# ---------------------------------------------------------------------------
#  User-Agent rotation
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
#  Price parsing
# ---------------------------------------------------------------------------
_PRICE_RE = re.compile(r"(?:₹|Rs\.?\s*|INR\s*)([\d,]+(?:\.[\d]+)?)")
_DISCOUNT_CONTEXT = re.compile(
    r"(?:discount|cut|drop|off|save|cashback|exchange|slashed)[\s\w]{0,15}?(?:₹|Rs\.?\s*|INR\s*)([\d,]+)",
    re.IGNORECASE,
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

# ---------------------------------------------------------------------------
#  Accessory / product-type detection
# ---------------------------------------------------------------------------
_ACCESSORY_WORDS = re.compile(
    r"\b(case|cover|pouch|sleeve|skin|protector|tempered\s*glass|screen\s*guard|"
    r"charger|cable|adapter|holder|stand|mount|strap|band|loop|sticker|decal|"
    r"back\s*cover|flip\s*cover|bumper|armor|wallet\s*case)\b",
    re.IGNORECASE,
)
_PHONE_BRANDS = {"iphone", "samsung", "pixel", "oneplus", "redmi", "realme", "poco",
                 "vivo", "oppo", "motorola", "moto", "nothing", "iqoo", "galaxy"}
_LAPTOP_WORDS = {"laptop", "macbook", "chromebook", "notebook"}
_WATCH_WORDS = {"watch", "smartwatch", "band"}
_TV_WORDS = {"tv", "television"}
_TABLET_WORDS = {"ipad", "tablet"}

def _refine_query(query: str) -> str:
    q_lower = query.lower()
    words = set(q_lower.split())
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
    return bool(_ACCESSORY_WORDS.search(title))

# ---------------------------------------------------------------------------
#  URL classification
# ---------------------------------------------------------------------------
_NEWS_DOMAINS = {
    "timesofindia", "indiatimes.com", "news18", "hindustantimes",
    "indianexpress", "youtube.com", "quora.com", "reddit.com",
    "twitter.com", "facebook.com", "gizmochina", "tomsguide",
    "techradar", "digit.in", "compareraja",
}
_TRUSTED_PRICE_SITES = {
    "91mobiles", "smartprix", "mysmartprice", "gadgets360",
    "pricebefore", "pricedekho", "gsmarena",
}

def _is_news_url(href: str) -> bool:
    h = href.lower()
    return any(nd in h for nd in _NEWS_DOMAINS)

def _is_trusted_price_site(href: str) -> bool:
    h = href.lower()
    return any(ts in h for ts in _TRUSTED_PRICE_SITES)

# ---------------------------------------------------------------------------
#  Title cleaning (Brave prefixes / breadcrumbs)
# ---------------------------------------------------------------------------
def _clean_brave_title(title: str, site_name: str) -> str:
    title = re.sub(
        r'^[A-Za-z0-9]+(?:\.[a-z0-9]+)*\.(?:com|in|org|net)[›\s]+(?:[^›]+[›\s]+)*',
        '', title,
    ).strip()
    title = re.sub(r'^\d{2}:\d{2}YouTube', '', title).strip()
    for prefix in [site_name, "Times of India", "YouTube", "My Mobile India",
                   "Gadgets360", "Smartprix", "91mobiles"]:
        if title.startswith(prefix):
            title = title[len(prefix):].strip()
    title = re.sub(r'^[›\-\|:]+\s*', '', title).strip()
    return title if title else f"{site_name} product"

# ---------------------------------------------------------------------------
#  Site configuration (domain ↔ display name ↔ search URL)
# ---------------------------------------------------------------------------
_SITE_CONFIG = {
    "amazon":   {"domain": "amazon.in",    "display": "Amazon",
                 "tpl": "https://www.amazon.in/s?k={q}"},
    "flipkart": {"domain": "flipkart.com", "display": "Flipkart",
                 "tpl": "https://www.flipkart.com/search?q={q}"},
    "myntra":   {"domain": "myntra.com",   "display": "Myntra",
                 "tpl": "https://www.myntra.com/{qh}"},
    "snapdeal": {"domain": "snapdeal.com", "display": "Snapdeal",
                 "tpl": "https://www.snapdeal.com/search?keyword={q}"},
    "ajio":     {"domain": "ajio.com",     "display": "Ajio",
                 "tpl": "https://www.ajio.com/search/?text={q}"},
    "tatacliq": {"domain": "tatacliq.com", "display": "TataCliq",
                 "tpl": "https://www.tatacliq.com/search/?searchCategory=all&text={q}"},
}

def _fallback_url(key: str, query: str) -> str:
    cfg = _SITE_CONFIG.get(key)
    if not cfg:
        return ""
    return cfg["tpl"].format(q=quote_plus(query), qh=query.replace(" ", "-"))

# ===================================================================
#  BATCH SEARCH — main entry point for price comparison
#  ONE search covers ALL sites → dramatically fewer HTTP requests
# ===================================================================

async def batch_search_all_sites(query: str, site_keys: List[str]) -> List[Product]:
    """Search for product prices across multiple sites using minimal HTTP requests.

    OLD approach: 4 strategies × 4 sites = 16+ HTTP requests → rate limiting
    NEW approach: 1 Brave + 1 DDG + 0-2 Bing = 2-4 HTTP requests total
    """
    refined = _refine_query(query)

    # Build domain → config lookup for requested sites
    sites: Dict[str, dict] = {}
    for key in site_keys:
        cfg = _SITE_CONFIG.get(key)
        if cfg:
            sites[cfg["domain"]] = {
                "key": key,
                "display": cfg["display"],
                "fallback": _fallback_url(key, query),
            }

    if not sites:
        return []

    all_products: List[Product] = []
    found_sites: Set[str] = set()

    # --- Strategy 1: ONE Brave search (covers all sites at once) ---
    try:
        brave_prods = await asyncio.wait_for(
            _brave_multi_search(refined, sites), timeout=12,
        )
        for p in brave_prods:
            if not _is_accessory(p.name):
                all_products.append(p)
                if p.price > 0:
                    found_sites.add(p.site)
    except (asyncio.TimeoutError, Exception):
        pass

    # --- Strategy 2: ONE DDG Lite search for missing sites ---
    missing = {d: c for d, c in sites.items() if c["display"] not in found_sites}
    if missing:
        try:
            ddg_prods = await asyncio.wait_for(
                _ddg_multi_search(refined, missing), timeout=12,
            )
            for p in ddg_prods:
                if not _is_accessory(p.name):
                    all_products.append(p)
                    if p.price > 0:
                        found_sites.add(p.site)
        except (asyncio.TimeoutError, Exception):
            pass

    # --- Strategy 3: Bing for still-missing (max 2 requests) ---
    still_missing = {d: c for d, c in sites.items() if c["display"] not in found_sites}
    bing_domains = list(still_missing.keys())[:2]
    if bing_domains:
        async def _try_bing(domain):
            try:
                cfg = still_missing[domain]
                return await _bing_search(refined, domain, cfg["display"], cfg["fallback"])
            except Exception:
                return []

        bing_results = await asyncio.gather(*[_try_bing(d) for d in bing_domains])
        for domain, prods in zip(bing_domains, bing_results):
            cfg = still_missing[domain]
            for p in prods:
                if not _is_accessory(p.name):
                    all_products.append(p)
                    if p.price > 0:
                        found_sites.add(cfg["display"])

    # --- Fallback entries for sites with zero results ---
    for domain, cfg in sites.items():
        if cfg["display"] not in found_sites:
            all_products.append(Product(
                name=f"{cfg['display']} {query}",
                price=0,
                url=cfg["fallback"],
                site=cfg["display"],
                rating=None,
                details=f"Click to search on {cfg['display']}",
            ))

    return all_products

# ===================================================================
#  BRAVE — single search, multi-site extraction
# ===================================================================

async def _brave_multi_search(query: str, sites: Dict[str, dict]) -> List[Product]:
    """ONE Brave search — extract prices for ALL target sites at once."""
    search_query = f"{query} price buy online India"
    url = "https://search.brave.com/search"

    async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
        resp = await client.get(url, params={"q": search_query, "country": "in"}, headers={
            "User-Agent": _USER_AGENTS[0],
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-IN,en;q=0.9",
        })
    if resp.status_code != 200:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    products: List[Product] = []
    per_site_count: Dict[str, int] = {}  # max 3 results per site

    for r in soup.select("#results .snippet, [data-type='web']")[:15]:
        title_el = r.select_one(".snippet-title, .title, h2 a, a")
        desc_el = r.select_one(".snippet-description, .snippet-content, .description")
        url_el = r.select_one("a[href^='http']")

        title = title_el.get_text(strip=True) if title_el else ""
        desc = desc_el.get_text(strip=True) if desc_el else ""
        href = url_el.get("href", "") if url_el else ""
        all_text = title + " " + desc

        if _is_news_url(href):
            continue

        price = _parse_price(all_text)
        if price <= 0:
            continue

        # Determine which target site this result belongs to
        matched_cfg = None

        # Tier 1: Direct product URL (amazon.in, flipkart.com, etc.)
        for domain, cfg in sites.items():
            if domain in href:
                matched_cfg = cfg
                break

        # Tier 2: Trusted comparison site mentioning a target store name
        if not matched_cfg and _is_trusted_price_site(href):
            all_lower = all_text.lower()
            for domain, cfg in sites.items():
                if cfg["display"].lower() in all_lower:
                    matched_cfg = cfg
                    break

        if not matched_cfg:
            continue

        display = matched_cfg["display"]
        if per_site_count.get(display, 0) >= 3:
            continue
        per_site_count[display] = per_site_count.get(display, 0) + 1

        product_url = href if any(d in href for d in sites) else matched_cfg["fallback"]
        clean_title = _clean_brave_title(title, display) if title else f"{display} {query}"

        products.append(Product(
            name=clean_title[:100], price=price, url=product_url,
            site=display, rating=None,
        ))

    return products

# ===================================================================
#  DDG LITE — single search, multi-site extraction
# ===================================================================

async def _ddg_multi_search(query: str, sites: Dict[str, dict]) -> List[Product]:
    """ONE DDG Lite search — extract prices for multiple sites."""
    search_query = f"{query} price buy online India"
    url = "https://lite.duckduckgo.com/lite/"

    async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
        resp = await client.post(url, data={"q": search_query}, headers={
            "User-Agent": _USER_AGENTS[1],
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html",
        })
    if resp.status_code != 200:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    products: List[Product] = []
    per_site_count: Dict[str, int] = {}

    for table in soup.select("table"):
        for link in table.select("a.result-link, td a[href^='http']"):
            title = link.get_text(strip=True)
            href = link.get("href", "")
            if "duckduckgo.com" in href or _is_news_url(href):
                continue

            parent_row = link.find_parent("tr")
            snippet = ""
            if parent_row:
                for nr in parent_row.find_next_siblings("tr", limit=2):
                    snippet += " " + nr.get_text(strip=True)

            all_text = title + " " + snippet
            price = _parse_price(all_text)
            if price <= 0:
                continue

            matched_cfg = None
            for domain, cfg in sites.items():
                if domain in href:
                    matched_cfg = cfg
                    break
            if not matched_cfg and _is_trusted_price_site(href):
                all_lower = all_text.lower()
                for domain, cfg in sites.items():
                    if cfg["display"].lower() in all_lower:
                        matched_cfg = cfg
                        break

            if not matched_cfg:
                continue

            display = matched_cfg["display"]
            if per_site_count.get(display, 0) >= 3:
                continue
            per_site_count[display] = per_site_count.get(display, 0) + 1

            product_url = href if any(d in href for d in sites) else matched_cfg["fallback"]
            products.append(Product(
                name=title[:100] if title else f"{display} {query}",
                price=price, url=product_url, site=display, rating=None,
            ))

    return products

# ===================================================================
#  BING — per-site fallback (used only for 1-2 still-missing sites)
# ===================================================================

async def _bing_search(query: str, site_domain: str, site_name: str, fallback_url: str) -> List[Product]:
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
                products.append(Product(
                    name=title[:100], price=price, url=href,
                    site=site_name, rating=None,
                ))
        if products:
            return products[:3]

        # Broader query without site: operator
        search_query2 = f"{query} price {site_name} India"
        bing_url2 = f"https://www.bing.com/search?q={quote_plus(search_query2)}&setlang=en&cc=IN"
        async with httpx.AsyncClient(follow_redirects=True, timeout=8) as client:
            resp2 = await client.get(bing_url2, headers=_get_headers(0))
        if resp2.status_code != 200:
            return []
        soup2 = BeautifulSoup(resp2.text, "html.parser")
        direct = []
        comparison = []
        for result in soup2.select("li.b_algo, .b_algo")[:6]:
            title_el = result.select_one("h2 a, h2")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            snippet = result.get_text(" ", strip=True)
            price = _parse_price(snippet)
            if price <= 0:
                continue
            if site_domain in href and not _is_news_url(href):
                direct.append(Product(
                    name=title[:100], price=price, url=href,
                    site=site_name, rating=None,
                ))
            elif _is_trusted_price_site(href) and site_name.lower() in snippet.lower():
                comparison.append(Product(
                    name=title[:100], price=price, url=fallback_url,
                    site=site_name, rating=None,
                ))
        return (direct or comparison)[:3]
    except Exception:
        return []

# ===================================================================
#  LEGACY — kept for backward compatibility with individual scrapers
# ===================================================================

async def google_price_search(query: str, site_domain: str, site_name: str, fallback_url: str) -> List[Product]:
    """Legacy single-site search. Prefer batch_search_all_sites for multi-site."""
    refined = _refine_query(query)

    async def _try(coro):
        try:
            return await coro
        except Exception:
            return []

    # Use DDG + Bing (save Brave for batch search to avoid rate limits)
    results = await asyncio.gather(
        _try(_ddg_single_search(refined, site_domain, site_name, fallback_url)),
        _try(_bing_search(refined, site_domain, site_name, fallback_url)),
    )

    for products in results:
        filtered = [p for p in products if not _is_accessory(p.name)]
        if filtered:
            return filtered
        if products:
            return products

    return [Product(
        name=f"{site_name} {query}", price=0, url=fallback_url,
        site=site_name, rating=None,
        details=f"Click to search on {site_name}",
    )]


async def _ddg_single_search(query: str, site_domain: str, site_name: str, fallback_url: str) -> List[Product]:
    """DDG Lite search for a single site (legacy)."""
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
        for table in soup.select("table"):
            for link in table.select("a.result-link, td a[href^='http']"):
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if "duckduckgo.com" in href or _is_news_url(href):
                    continue
                parent_row = link.find_parent("tr")
                snippet = ""
                if parent_row:
                    for nr in parent_row.find_next_siblings("tr", limit=2):
                        snippet += " " + nr.get_text(strip=True)
                all_text = title + " " + snippet
                if site_domain not in href:
                    continue
                price = _parse_price(all_text)
                if price > 0:
                    products.append(Product(
                        name=title[:100], price=price, url=href,
                        site=site_name, rating=None,
                    ))
        return products[:3]
    except Exception:
        return []

# ===================================================================
#  BRAVE WEB SEARCH — for chat grounding
# ===================================================================

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
