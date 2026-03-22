"""Quick test for batch search debugging."""
import asyncio
import httpx
from bs4 import BeautifulSoup
import re

_PRICE_RE = re.compile(r"(?:₹|Rs\.?\s*|INR\s*)([\d,]+(?:\.[\d]+)?)")

async def debug_brave():
    url = "https://search.brave.com/search"
    q = "iPhone 15 smartphone price buy online India"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-IN,en;q=0.9",
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
        resp = await client.get(url, params={"q": q, "country": "in"}, headers=headers)
    print(f"Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Response length: {len(resp.text)}")
        print(resp.text[:500])
        return

    soup = BeautifulSoup(resp.text, "html.parser")

    # Try different selectors
    for selector in ["#results .snippet", "[data-type='web']", ".fdb", ".snippet", ".result"]:
        matches = soup.select(selector)
        print(f"Selector '{selector}': {len(matches)} matches")

    # Get all links with prices
    all_text = soup.get_text(" ")
    prices = _PRICE_RE.findall(all_text)
    print(f"\nPrices in page text: {prices[:10]}")

    # Try broader extraction
    for a in soup.select("a[href]")[:20]:
        href = a.get("href", "")
        text = a.get_text(" ").strip()[:100]
        if any(d in href for d in ["amazon.in", "flipkart.com", "snapdeal.com"]):
            print(f"\nTarget link: {href[:80]}")
            print(f"  Text: {text}")

    # Save HTML for inspection
    with open("debug_brave.html", "w", encoding="utf-8") as f:
        f.write(resp.text)
    print("\nSaved full HTML to debug_brave.html")

async def test_batch():
    from scrapers._google_helper import batch_search_all_sites
    sites = ["amazon", "flipkart", "snapdeal"]
    products = await batch_search_all_sites("Samsung Galaxy S25", sites)
    print(f"\n=== Batch search results ({len(products)} products) ===")
    for p in products:
        print(f"  [{p.site}] {p.name[:60]} - Rs {p.price}")
        print(f"    URL: {p.url[:70]}")

async def debug_ddg():
    """Debug DDG Lite response."""
    url = "https://lite.duckduckgo.com/lite/"
    q = "iPhone 15 smartphone price buy online India"
    async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
        resp = await client.post(url, data={"q": q}, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html",
        })
    print(f"DDG Status: {resp.status_code}")
    soup = BeautifulSoup(resp.text, "html.parser")

    # Check what links exist
    tables = soup.select("table")
    print(f"Tables: {len(tables)}")
    links = soup.select("a[href]")
    print(f"Total links: {len(links)}")

    for link in links[:15]:
        href = link.get("href", "")
        text = link.get_text(" ").strip()[:80]
        if "duckduckgo" not in href and href.startswith("http"):
            parent = link.find_parent("tr")
            snippet = ""
            if parent:
                for nr in parent.find_next_siblings("tr", limit=2):
                    snippet += " " + nr.get_text(" ").strip()[:80]
            prices = _PRICE_RE.findall(text + " " + snippet)
            print(f"  {text[:60]}")
            print(f"  URL: {href[:70]}")
            if prices:
                print(f"  PRICES: {prices}")
            print()

    with open("debug_ddg.html", "w", encoding="utf-8") as f:
        f.write(resp.text)
    print("Saved DDG HTML to debug_ddg.html")

async def debug_bing():
    """Debug Bing response."""
    from urllib.parse import quote_plus
    q = "iPhone 15 smartphone price site:amazon.in"
    bing_url = f"https://www.bing.com/search?q={quote_plus(q)}&setlang=en&cc=IN"
    async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
        resp = await client.get(bing_url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
        })
    print(f"\nBing Status: {resp.status_code}")
    soup = BeautifulSoup(resp.text, "html.parser")
    results = soup.select("li.b_algo, .b_algo")
    print(f"Bing results: {len(results)}")
    for r in results[:5]:
        title_el = r.select_one("h2 a, h2")
        title = title_el.get_text(" ").strip()[:80] if title_el else "(no title)"
        href = title_el.get("href", "") if title_el else ""
        all_text = r.get_text(" ").strip()[:200]
        prices = _PRICE_RE.findall(all_text)
        print(f"  {title}")
        print(f"  URL: {href[:70]}")
        if prices:
            print(f"  PRICES: {prices}")
        print()

    with open("debug_bing.html", "w", encoding="utf-8") as f:
        f.write(resp.text)
    print("Saved Bing HTML to debug_bing.html")

if __name__ == "__main__":
    asyncio.run(debug_ddg())
    asyncio.run(debug_bing())
