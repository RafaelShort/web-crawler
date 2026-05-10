import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.queue.queue_manager import QueueManager, CrawlMessage


async def main():
    queue = QueueManager()
    await queue.connect()

    # ── Publicar URLs ──────────────────────────────────────────
    print("Publicando URLs na fila...\n")

    urls = [
        "https://example.com",
        "https://python.org",
        "https://github.com",
    ]

    await queue.publish_many(urls, depth=0, source_url="seed")

    # ── Verificar tamanho da fila ──────────────────────────────
    size = await queue.get_queue_size()
    print(f"Mensagens na fila: {size}\n")

    # ── Consumir mensagens ─────────────────────────────────────
    print("Consumindo mensagens...\n")

    consumed = []

    async def handler(message: CrawlMessage) -> bool:
        consumed.append(message)
        print(f"  ✅ Recebido: {message.url} (depth={message.depth})")
        return True

    # Consumir com timeout
    try:
        await asyncio.wait_for(queue.consume(handler), timeout=3.0)
    except asyncio.TimeoutError:
        pass

    # ── Estatísticas ───────────────────────────────────────────
    print("\nEstatísticas:")
    for k, v in queue.stats().items():
        print(f"  {k}: {v}")

    await queue.disconnect()


asyncio.run(main())
