import httpx, asyncio, re
from bs4 import BeautifulSoup

async def check():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept-Language": "en-IN,en;q=0.9",
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as c:
        # DDG for Flipkart
        r = await c.get("https://html.duckduckgo.com/html/?q=iPhone+15+price+Flipkart", headers=headers)
        print(f"DDG: status={r.status_code}")
        soup = BeautifulSoup(r.text, "html.parser")
        for i, res in enumerate(soup.select(".result")[:6]):
            title_el = res.select_one(".result__a")
            snippet_el = res.select_one(".result__snippet")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            href = title_el.get("href", "")
            if "uddg=" in href:
                from urllib.parse import unquote
                href = unquote(href.split("uddg=")[1].split("&")[0])
            all_text = title + " " + snippet
            has_fk = "flipkart" in all_text.lower() or "flipkart" in href
            prices = re.findall(r"(?:₹|Rs\.?\s*)([\d,]+(?:\.[\d]+)?)", all_text)
            real = [float(p.replace(",", "")) for p in prices if float(p.replace(",", "")) > 100]
            print(f"\n#{i+1} [{'FK' if has_fk else '  '}] {title[:80]}")
            print(f"   href: {href[:80]}")
            print(f"   prices: {real}")
            print(f"   snippet: {snippet[:200]}")

        # Also DDG for Amazon
        print("\n\n=== DDG for Amazon ===")
        r2 = await c.get("https://html.duckduckgo.com/html/?q=iPhone+15+price+Amazon", headers=headers)
        soup2 = BeautifulSoup(r2.text, "html.parser")
        for i, res in enumerate(soup2.select(".result")[:6]):
            title_el = res.select_one(".result__a")
            snippet_el = res.select_one(".result__snippet")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            href = title_el.get("href", "")
            if "uddg=" in href:
                from urllib.parse import unquote
                href = unquote(href.split("uddg=")[1].split("&")[0])
            all_text = title + " " + snippet
            has_az = "amazon" in all_text.lower() or "amazon" in href
            prices = re.findall(r"(?:₹|Rs\.?\s*)([\d,]+(?:\.[\d]+)?)", all_text)
            real = [float(p.replace(",", "")) for p in prices if float(p.replace(",", "")) > 100]
            print(f"\n#{i+1} [{'AZ' if has_az else '  '}] {title[:80]}")
            print(f"   href: {href[:80]}")
            print(f"   prices: {real}")

asyncio.run(check())
