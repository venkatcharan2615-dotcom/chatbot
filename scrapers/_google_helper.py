from models import Product
from typing import List, Dict, Set
import re
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus

# DDGS package — handles DDG's anti-bot measures properly
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

_executor = ThreadPoolExecutor(max_workers=3)

# ---------------------------------------------------------------------------
#  Price parsing
# ---------------------------------------------------------------------------
_PRICE_RE = re.compile(r"(?:₹|Rs\.?\s*|INR\s*)([\d,]+(?:\.[\d]+)?)")

def _parse_price(text: str) -> float:
    """Extract median price from text, ignoring discount/cashback amounts."""
    discount_ctx = re.compile(
        r"(?:discount|cut|drop|off|save|cashback|exchange|slashed|down by)[\s\w]{0,15}?"
        r"(?:₹|Rs\.?\s*|INR\s*)([\d,]+)", re.IGNORECASE,
    )
    discount_amounts = set()
    for m in discount_ctx.findall(text):
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


def _extract_price_near_store(text: str, store_lower: str) -> float:
    """Find a price that appears within ~80 chars of a store name mention.

    Skips amounts that appear in discount/savings context (e.g. 'Rs 9,901 discount').
    """
    _DISCOUNT_NEAR = re.compile(
        r"(?:discount|off|save|cashback|drop(?:s|ped)?(?:\s+(?:by|to))?\s+(?:over\s+)?(?:Rs\.?\s*|₹|INR\s*)"
        r"|(?:Rs\.?\s*|₹|INR\s*)[\d,]+\s*(?:discount|off|cashback|cheaper))",
        re.IGNORECASE,
    )
    t_lower = text.lower()
    idx = 0
    candidates = []
    while True:
        pos = t_lower.find(store_lower, idx)
        if pos < 0:
            break
        # Window around the store mention
        start = max(0, pos - 120)
        end = min(len(text), pos + len(store_lower) + 120)
        window = text[start:end]

        # Collect discount amounts in this window to exclude them
        discount_amounts = set()
        # Pattern: "discount/off/save... Rs X" and "discount of up to Rs X"
        for dm in re.findall(r"(?:discount|off|save|cashback|drop\w*\s+(?:by|of|to)\s+(?:over\s+|up\s+to\s+)?)"
                             r"(?:Rs\.?\s*|₹|INR\s*)([\d,]+)", window, re.IGNORECASE):
            try:
                discount_amounts.add(float(dm.replace(",", "")))
            except ValueError:
                pass
        # Pattern: "Rs X discount/off/cashback/cheaper"
        for dm in re.findall(r"(?:Rs\.?\s*|₹|INR\s*)([\d,]+)\s*(?:discount|off|cashback|cheaper)",
                             window, re.IGNORECASE):
            try:
                discount_amounts.add(float(dm.replace(",", "")))
            except ValueError:
                pass
        # Pattern: "up to Rs X discount/off" or "upto Rs X off"
        for dm in re.findall(r"up\s*to\s+(?:Rs\.?\s*|₹|INR\s*)([\d,]+)\s*(?:discount|off)?",
                             window, re.IGNORECASE):
            try:
                discount_amounts.add(float(dm.replace(",", "")))
            except ValueError:
                pass

        for m in _PRICE_RE.findall(window):
            try:
                p = float(m.replace(",", ""))
                if 500 < p < 10_000_000 and p not in discount_amounts:
                    candidates.append(p)
            except ValueError:
                pass
        idx = pos + 1
    if not candidates:
        return 0
    candidates.sort()
    return candidates[len(candidates) // 2]

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

# Product variant keywords — if these appear in a result but NOT in the query,
# the result is for a different product variant and should be excluded.
# ONLY applies to electronics with a brand+model number pattern.
_VARIANT_WORDS = {"pro", "plus", "ultra", "max", "mini", "lite", "se",
                  "fe", "neo", "turbo", "slim", "note"}

# Brands where variant keywords actually mean a different SKU/price tier
_VARIANT_BRANDS = _PHONE_BRANDS | {"ipad", "macbook", "surface", "tab",
                                    "redmi", "poco", "narzo", "gt"}

# Pattern: a number (model number) in the query, e.g. "iPhone 17", "Galaxy S25"
_MODEL_NUMBER_RE = re.compile(r"\d")

def _has_variant_mismatch(query_lower: str, title_lower: str) -> bool:
    """Return True if the title is for a different product variant than the query.

    Only applies when the query looks like an electronics product with a model
    number (e.g. 'iPhone 17', 'Samsung Galaxy S25', 'Realme Narzo 70').
    Does NOT apply to generic products like 'boAt headphones' or 'Nike shoes'
    where 'Pro' is just a model name, not a price-tier variant.
    """
    q_words = set(query_lower.split())

    # Only check for variant mismatch on electronics with a model number
    has_brand = bool(q_words & _VARIANT_BRANDS)
    has_number = bool(_MODEL_NUMBER_RE.search(query_lower))
    if not (has_brand and has_number):
        return False

    t_words = set(title_lower.split())
    title_variants = t_words & _VARIANT_WORDS
    query_variants = q_words & _VARIANT_WORDS
    # If the title has variant words NOT present in the query → mismatch
    return bool(title_variants - query_variants)

# ---------------------------------------------------------------------------
#  URL / domain classification
# ---------------------------------------------------------------------------
# Only filter truly irrelevant sites (social, video, forums)
# DO NOT filter news/tech sites — they contain price information!
_JUNK_DOMAINS = {
    "youtube.com", "quora.com", "reddit.com", "twitter.com", "facebook.com",
    "instagram.com", "pinterest.com", "tiktok.com",
    "zhihu.com", "android-hilfe.de", "ctiforum.com", "syzer.com.br",
}

def _is_junk_url(href: str) -> bool:
    h = href.lower()
    return any(nd in h for nd in _JUNK_DOMAINS)

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
#  BATCH SEARCH — main entry point
#  Strategy: Mine DDGS snippets for store+price pairs
# ===================================================================

async def batch_search_all_sites(query: str, site_keys: List[str]) -> List[Product]:
    """Search for product prices across multiple sites using DDGS snippet mining."""
    refined = _refine_query(query)

    # Build config for requested sites
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

    # --- Strategy 1: DDGS snippet mining (fast, reliable) ---
    ddgs_results = {}
    try:
        ddgs_results = await asyncio.wait_for(
            _ddgs_mine_prices(refined, query, sites), timeout=20,
        )
    except (asyncio.TimeoutError, BaseException):
        pass

    found_sites: Set[str] = set()
    all_products: List[Product] = []

    # First pass: compute per-site median price
    site_prices: Dict[str, float] = {}
    for display, info in ddgs_results.items():
        prices = info["prices"]
        if prices:
            prices.sort()
            median = prices[len(prices) // 2]
            filtered = [p for p in prices if median / 5 <= p <= median * 5]
            if filtered:
                filtered.sort()
                site_prices[display] = filtered[len(filtered) // 2]
            else:
                site_prices[display] = median

    # Cross-site outlier filter: if a site's price is >8x away from the
    # cross-site median, it's likely a wrong product (accessory, etc.)
    if len(site_prices) >= 2:
        cross_vals = sorted(site_prices.values())
        cross_median = cross_vals[len(cross_vals) // 2]
        for display in list(site_prices):
            p = site_prices[display]
            if p < cross_median / 8 or p > cross_median * 8:
                del site_prices[display]

    for display, info in ddgs_results.items():
        url = info["url"]
        title = info["title"]
        if display in site_prices:
            all_products.append(Product(
                name=title, price=site_prices[display], url=url, site=display, rating=None,
            ))
            found_sites.add(display)
        elif url != info.get("fallback", ""):
            # Have a direct URL but no price — still useful
            all_products.append(Product(
                name=title, price=0, url=url, site=display, rating=None,
            ))

    # --- Fallback entries for sites that still have zero results ---
    for domain, cfg in sites.items():
        if cfg["display"] not in {p.site for p in all_products}:
            all_products.append(Product(
                name=f"{cfg['display']} – Search for {query}",
                price=0, url=cfg["fallback"], site=cfg["display"],
                rating=None, details=f"Click to search on {cfg['display']}",
            ))

    return all_products


async def inspect_batch_search(query: str, site_keys: List[str]) -> dict:
    """Return raw DDGS mining diagnostics for a query."""
    refined = _refine_query(query)
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
        return {"query": query, "refined_query": refined, "sites": {}, "error": "no_valid_sites"}

    try:
        raw = await asyncio.wait_for(_ddgs_mine_prices(refined, query, sites), timeout=20)
    except (asyncio.TimeoutError, BaseException) as exc:
        return {
            "query": query,
            "refined_query": refined,
            "sites": {},
            "error": type(exc).__name__,
        }

    diagnostics = {}
    for display, info in raw.items():
        diagnostics[display] = {
            "prices": info.get("prices", []),
            "url": info.get("url"),
            "fallback": info.get("fallback"),
            "title": info.get("title"),
            "details": info.get("details"),
        }
    return {"query": query, "refined_query": refined, "sites": diagnostics, "error": None}


# ===================================================================
#  DDGS SNIPPET MINING — extract store+price pairs from ALL results
# ===================================================================

def _ddgs_mine_prices_sync(query: str, original_query: str, sites: Dict[str, dict]) -> dict:
    """Mine DDGS search snippets for store+price pairs.

    Instead of matching results 1:1 to stores, we scan ALL snippets
    for mentions of each store near a price. This catches price data
    from news articles, deal sites, comparison sites, etc.

    Returns: {display_name: {"prices": [...], "url": best_url, "title": title, "fallback": url}}
    """
    site_names = " ".join(cfg["display"] for cfg in sites.values())

    # Four complementary queries to maximize price coverage
    queries = [
        f"{query} price India {site_names}",
        f"{query} price Rs buy online India",
        f"{query} lowest price best deal India {site_names}",
        f"{original_query} buy online Rs price",
    ]

    # Collect all raw results using daemon threads (so hung queries don't block)
    all_results = []
    for search_q in queries:
        batch = []
        def _run(q=search_q, out=batch):
            try:
                out.extend(DDGS(timeout=5).text(q, region="in-en", max_results=12))
            except Exception:
                pass
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=8)  # Hard per-query timeout
        all_results.extend(batch)

    # Per-site tracking
    site_data: Dict[str, dict] = {}
    for domain, cfg in sites.items():
        site_data[cfg["display"]] = {
            "prices": [],
            "url": cfg["fallback"],  # default to search URL
            "title": f"{original_query} on {cfg['display']}",
            "details": "",
            "fallback": cfg["fallback"],
            "domain": domain,
        }

    seen_hrefs: Set[str] = set()
    # Build relevance check: significant query words
    # Include numbers (e.g. "15" in "iPhone 15") and words > 2 chars
    _STOP = {"price", "india", "online", "buy", "best", "search", "new", "the", "for", "and", "with"}
    query_sig = [w for w in original_query.lower().split()
                 if (len(w) > 2 and w not in _STOP) or w.isdigit()]

    for r in all_results:
        title = r.get("title", "")
        href = r.get("href", "")
        body = r.get("body", "")

        # De-duplicate results across queries
        if href in seen_hrefs:
            continue
        seen_hrefs.add(href)

        # Skip social/video
        if _is_junk_url(href):
            continue

        all_text = title + " " + body
        text_lower = all_text.lower()

        # Relevance check: does this result mention significant query words?
        relevance = sum(1 for w in query_sig if w in text_lower) if query_sig else 1
        is_relevant = relevance >= max(1, len(query_sig) // 2)

        # Collect store mentions with their positions for disambiguation
        snippet_store_prices: Dict[str, list] = {}  # display -> [(price, position)]

        for domain, cfg in sites.items():
            display = cfg["display"]
            display_lower = display.lower()
            info = site_data[display]

            is_direct = domain in href
            is_mentioned = display_lower in text_lower

            if not is_direct and not is_mentioned:
                continue

            # Variant mismatch check: skip results for different product variants
            # e.g. query="iPhone 17" but result="iPhone 17 Pro"
            variant_mismatch = _has_variant_mismatch(
                original_query.lower(), title.lower(),
            )

            # Direct e-commerce URL — save as best URL (prefer product pages over search)
            if is_direct and info["url"] == info["fallback"]:
                if not _is_accessory(title) and is_relevant and not variant_mismatch:
                    info["url"] = href
                    if title:
                        clean = title[:100]
                        for prefix in ["Amazon.in: ", "Buy ", "Flipkart: "]:
                            if clean.startswith(prefix):
                                clean = clean[len(prefix):]
                        info["title"] = clean
                    if body:
                        info["details"] = body[:160]

            # Skip price extraction from irrelevant or variant-mismatched results
            if not is_relevant or variant_mismatch:
                continue

            # Extract price near this store's mention
            price = _extract_price_near_store(all_text, display_lower)
            if price > 0:
                # Find position of closest store mention for disambiguation
                pos = text_lower.find(display_lower)
                snippet_store_prices[display] = (price, pos if pos >= 0 else 9999)

        # Disambiguation: if multiple stores in the same snippet got the exact
        # same price, only assign it to the store whose name is closest to a
        # price token in the text — the others are likely reading the same number.
        if len(snippet_store_prices) > 1:
            prices_seen: Dict[float, list] = {}
            for disp, (pr, pos) in snippet_store_prices.items():
                prices_seen.setdefault(pr, []).append((disp, pos))

            for pr, stores_pos in prices_seen.items():
                if len(stores_pos) > 1:
                    # Multiple stores got the same price from this snippet.
                    # Find which store mention is closest to a price mention.
                    price_positions = [m.start() for m in _PRICE_RE.finditer(all_text)]
                    if price_positions:
                        best_store = min(
                            stores_pos,
                            key=lambda sp: min(abs(sp[1] - pp) for pp in price_positions),
                        )
                        # Only keep the closest store; remove duplicates
                        for disp, pos in stores_pos:
                            if disp != best_store[0]:
                                del snippet_store_prices[disp]

        # Now add the surviving prices
        for display, (price, _pos) in snippet_store_prices.items():
            site_data[display]["prices"].append(price)

    return site_data


async def _ddgs_mine_prices(query: str, original_query: str, sites: Dict[str, dict]) -> dict:
    """Async wrapper — runs sync DDGS in thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor, _ddgs_mine_prices_sync, query, original_query, sites,
    )

# ===================================================================
#  LEGACY — kept for backward compatibility (grocery scrapers etc.)
# ===================================================================

async def google_price_search(query: str, site_domain: str, site_name: str, fallback_url: str) -> List[Product]:
    """Single-site search using DDGS snippet mining."""
    refined = _refine_query(query)
    sites = {site_domain: {"key": site_name.lower(), "display": site_name, "fallback": fallback_url}}

    try:
        result = await asyncio.wait_for(
            _ddgs_mine_prices(refined, query, sites), timeout=15,
        )
        info = result.get(site_name, {})
        prices = info.get("prices", [])
        if prices:
            prices.sort()
            return [Product(
                name=info.get("title", f"{site_name} {query}"),
                price=prices[len(prices) // 2],
                url=info.get("url", fallback_url),
                site=site_name, rating=None,
            )]
    except (asyncio.TimeoutError, BaseException):
        pass

    return [Product(
        name=f"{site_name} {query}", price=0, url=fallback_url,
        site=site_name, rating=None,
        details=f"Click to search on {site_name}",
    )]

# ===================================================================
#  WEB SEARCH — for chat grounding
# ===================================================================

def _web_search_sync(query: str) -> str:
    """Synchronous web search for chat AI grounding."""
    results_holder = []
    def _run():
        try:
            results_holder.extend(DDGS(timeout=5).text(query, region="in-en", max_results=5))
        except Exception:
            pass
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=8)
    snippets = []
    for r in results_holder:
        title = r.get("title", "")
        body = r.get("body", "")
        if title:
            snippets.append(f"- {title}: {body[:150]}" if body else f"- {title}")
    return "\n".join(snippets)


async def brave_web_search(query: str) -> str:
    """Search the web and return text snippets for AI grounding."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _web_search_sync, query)




