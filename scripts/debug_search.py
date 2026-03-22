import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scrapers._google_helper import inspect_batch_search


DEFAULT_SITES = ["amazon", "flipkart", "myntra", "snapdeal", "ajio", "tatacliq"]
DEFAULT_QUERIES = [
    "iphone 15",
    "samsung galaxy s24",
    "nike running shoes",
    "milk",
    "laptop under 50000",
]


async def main() -> None:
    for query in DEFAULT_QUERIES:
        diagnostics = await inspect_batch_search(query, DEFAULT_SITES)
        print("=" * 80)
        print(f"QUERY: {query}")
        print(json.dumps(diagnostics, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
