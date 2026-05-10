import sys
import os
import asyncio
import signal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.crawler.engine import CrawlerEngine


async def main():
    engine = CrawlerEngine()

    seed_urls = [
        "https://example.com",
        "https://python.org",
    ]

    print("🚀 Iniciando CrawlerEngine...\n")

    # Rodar por 15 segundos e encerrar
    try:
        await asyncio.wait_for(
            engine.start(seed_urls),
            timeout=15.0,
        )
    except asyncio.TimeoutError:
        print("\n⏱️  Tempo limite atingido, encerrando...\n")
        await engine.shutdown()

    # Estatísticas finais
    print("\n📊 Estatísticas finais:")
    stats = engine.stats()
    print(f"  Processadas : {stats['processed']}")
    print(f"  Ignoradas   : {stats['skipped']}")
    print(f"  Erros       : {stats['errors']}")
    print(f"  BloomFilter : {stats['bloom_size']} URLs")
    print(f"\n  MongoDB:")
    for k, v in stats['mongo'].items():
        print(f"    {k}: {v}")
    print(f"\n  Queue:")
    for k, v in stats['queue'].items():
        print(f"    {k}: {v}")


asyncio.run(main())
