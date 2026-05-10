import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.crawler.politeness import PolitenessPolicy


async def main():
    policy = PolitenessPolicy(
        rate_limit_delay=1.0,
        respect_robots_txt=True,
        user_agent="WebCrawler/1.0",
    )

    urls = [
        "https://python.org",
        "https://python.org/docs",
        "https://example.com",
    ]

    print("Testando politeness policy:\n")

    for url in urls:
        allowed = await policy.is_allowed(url)
        status = "✅ permitida" if allowed else "❌ bloqueada"
        print(f"  {status} → {url}")

    print()
    print("Estatisticas:")
    for k, v in policy.stats().items():
        print(f"  {k}: {v}")


asyncio.run(main())
