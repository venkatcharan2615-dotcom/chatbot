import httpx, asyncio, json

async def test():
    r = await httpx.AsyncClient(timeout=60).post(
        "http://127.0.0.1:8103/chatbot/compare",
        json={"query": "iPhone 15", "sites": ["amazon", "flipkart"]}
    )
    d = r.json()
    bp = d["best_product"]
    print(f"BEST: {bp['site']} - Rs {bp['price']} - {bp['name'][:60]}")
    print()
    for p in d["all_products"]:
        print(f"  {p['site']:10s} Rs {p['price']:>10.0f}  {p['name'][:60]}")

asyncio.run(test())
