import httpx, time, json

start = time.time()
r = httpx.post("http://localhost:8107/chatbot/compare", json={"query": "pixel 8"}, timeout=120)
elapsed = time.time() - start
d = json.loads(r.text)
print(f"Done in {elapsed:.1f}s | Status: {r.status_code} | Products: {len(d['all_products'])}")
for p in d["all_products"]:
    print(f"  {p['site']:12s} Rs {p['price']:>10,.0f}  {p['name'][:50]}")
print(f"Summary: {d['summary'][:120]}...")
