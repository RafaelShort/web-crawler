import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.crawler.fetcher import Fetcher


async def main():
    fetcher = Fetcher()

    urls = [
        "https://example.com",
        "https://python.org",
        "https://httpbin.org/status/404",
    ]

    print("Testando fetcher:\n")

    for url in urls:
        result = await fetcher.fetch(url)
        print(f"  URL        : {url}")
        print(f"  Status     : {result.status_code}")
        print(f"  Sucesso    : {result.success}")
        print(f"  Tempo      : {result.elapsed_ms:.0f}ms")
        print(f"  HTML size  : {len(result.html)} chars")
        if result.error:
            print(f"  Erro       : {result.error}")
        print()

    print("Estatisticas finais:")
    for k, v in fetcher.stats().items():
        print(f"  {k}: {v}")


asyncio.run(main())
