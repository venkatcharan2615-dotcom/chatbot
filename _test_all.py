import httpx, asyncio, json

async def test():
    c = httpx.AsyncClient(timeout=60)

    # Test homepage
    r = await c.get("http://127.0.0.1:8104/")
    print(f"Homepage: {r.status_code}")
    print(f"  Has Compare tab: {'Compare' in r.text}")
    print(f"  Has Chat tab: {'Chat' in r.text}")
    print(f"  Has Zepto: {'Zepto' in r.text}")
    print(f"  Has Zomato: {'Zomato' in r.text}")
    print(f"  Has Instamart: {'Instamart' in r.text}")

    # Test chat endpoint
    print("\nChat test:")
    r2 = await c.post("http://127.0.0.1:8104/chatbot/chat", json={"message": "What is the best phone under 30000?"})
    print(f"  Status: {r2.status_code}")
    d = r2.json()
    print(f"  Reply: {d['reply'][:150]}")

    # Test compare with new sites
    print("\nCompare test (amazon + zepto):")
    r3 = await c.post("http://127.0.0.1:8104/chatbot/compare", json={"query": "milk", "sites": ["amazon", "zepto"]})
    print(f"  Status: {r3.status_code}")
    d3 = r3.json()
    for p in d3["all_products"]:
        print(f"  {p['site']:10s} Rs {p['price']:>8.0f}  {p['name'][:50]}")

    await c.aclose()

asyncio.run(test())
