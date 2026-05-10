import asyncio
from loguru import logger

from src.config import get_settings
from src.crawler.bloom_filter import BloomFilter
from src.crawler.fetcher import Fetcher
from src.crawler.parser import Parser
from src.crawler.politeness import PolitenessPolicy
from src.storage.mongo_client import MongoStorage
from src.storage.elastic_client import ElasticStorage
from src.queue.queue_manager import QueueManager, CrawlMessage


class CrawlerEngine:
    """
    Motor principal do crawler.

    Orquestra todos os componentes:
    - BloomFilter      → deduplicação de URLs em memória
    - PolitenessPolicy → robots.txt + rate limiting
    - Fetcher          → download das páginas
    - Parser           → extração de conteúdo e links
    - MongoStorage     → persistência dos dados
    - ElasticStorage   → indexação para busca
    - QueueManager     → fila de URLs para crawling
    """

    def __init__(self):
        settings = get_settings()

        self.max_depth = settings.max_depth
        self.max_workers = settings.max_workers

        # Componentes 
        self.politeness = PolitenessPolicy(
            rate_limit_delay=settings.rate_limit_delay,
            respect_robots_txt=settings.respect_robots_txt,
            user_agent=settings.user_agent,
        )
        self.fetcher = Fetcher(politeness=self.politeness)
        self.parser = Parser()
        self.bloom = BloomFilter(capacity=1_000_000, error_rate=0.01)
        self.mongo = MongoStorage()
        self.elastic = ElasticStorage()
        self.queue = QueueManager()

        # Controle de workers
        self._semaphore: asyncio.Semaphore | None = None
        self._running = False

        # Estatísticas
        self._processed = 0
        self._skipped = 0
        self._errors = 0
        self._cached_stats: dict | None = None  

        logger.info(
            f"CrawlerEngine inicializado | "
            f"max_depth={self.max_depth} | "
            f"max_workers={self.max_workers}"
        )

    # Inicialização 

    async def start(self, seed_urls: list[str]) -> None:
        """
        Inicia o crawler com as URLs semente.

        Args:
            seed_urls: lista de URLs iniciais para crawling
        """
        await self.queue.connect()

        self._semaphore = asyncio.Semaphore(self.max_workers)
        self._running = True

        # Publicar seeds na fila 
        logger.info(f"🌱 Publicando {len(seed_urls)} seed URLs na fila...")
        await self.queue.publish_many(seed_urls, depth=0, source_url="seed")

        # Iniciar workers
        logger.info(f"Iniciando {self.max_workers} workers...")

        workers = [
            asyncio.create_task(self._worker(worker_id=i))
            for i in range(self.max_workers)
        ]

        try:
            await asyncio.gather(*workers)
        except asyncio.CancelledError:
            logger.info("Workers cancelados")
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Encerra o crawler e fecha conexões."""
        self._running = False

        # Cachear stats antes de fechar as conexões
        self._cached_stats = {
            "processed": self._processed,
            "skipped": self._skipped,
            "errors": self._errors,
            "bloom_size": len(self.bloom),
            "fetcher": self.fetcher.stats(),
            "mongo": self.mongo.stats(),
            "queue": self.queue.stats(),
        }

        self._log_stats()

        await self.queue.disconnect()
        self.mongo.close()
        self.elastic.close()
        logger.info("CrawlerEngine encerrado")

    # Workers

    async def _worker(self, worker_id: int) -> None:
        """Worker que consome mensagens da fila e processa URLs."""
        logger.info(f"Worker {worker_id} iniciado")

        async def handler(message: CrawlMessage) -> bool:
            async with self._semaphore:
                return await self._process(message, worker_id)

        try:
            await self.queue.consume(handler)
        except Exception as e:
            logger.error(f"Worker {worker_id} encerrado com erro: {e}")

    # Processamento de URL

    async def _process(self, message: CrawlMessage, worker_id: int) -> bool:
        """
        Processa uma mensagem da fila.
        """
        url = message.url
        depth = message.depth

        logger.info(f"[W{worker_id}] 🔍 Processando (depth={depth}): {url}")

        # 1. Verificar profundidade máxima
        if depth > self.max_depth:
            logger.debug(f"Profundidade máxima atingida: {url}")
            self._skipped += 1
            return True

        # 2. Verificar BloomFilter
        if url in self.bloom:
            logger.debug(f"URL já visitada (bloom): {url}")
            self._skipped += 1
            return True

        # 3. Verificar MongoDB
        if self.mongo.url_exists(url):
            logger.debug(f"URL já persistida (mongo): {url}")
            self.bloom.add(url)
            self._skipped += 1
            return True

        # 4. Marcar no BloomFilter antes do fetch
        self.bloom.add(url)

        # 5. Fazer o fetch 
        fetch_result = await self.fetcher.fetch(url)

        if not fetch_result.success:
            self.mongo.save_error(fetch_result)
            self._errors += 1
            return True

        # 6. Parsear o HTML
        try:
            parse_result = self.parser.parse(fetch_result.html, url)
        except Exception as e:
            logger.error(f"Erro ao parsear {url}: {e}")
            self._errors += 1
            return False

        # 7. Persistir no MongoDB e ElasticSearch
        self.mongo.save_page(fetch_result, parse_result, depth)
        self.elastic.index_page(fetch_result, parse_result, depth)
        self._processed += 1

        logger.info(
            f"[W{worker_id}] ✅ {url} | "
            f"links={len(parse_result.links)} | "
            f"words={parse_result.word_count}"
        )

        # 8. Publicar links descobertos na fila
        if depth < self.max_depth:
            new_links = [
                link for link in parse_result.links
                if link not in self.bloom
            ]

            if new_links:
                await self.queue.publish_many(
                    new_links,
                    depth=depth + 1,
                    source_url=url,
                )
                logger.debug(
                    f"[W{worker_id}] 📤 {len(new_links)} novos links publicados"
                )

        return True

    # Estatísticas

    def _log_stats(self) -> None:
        """Loga estatísticas finais do crawler."""
        s = self._cached_stats or self.stats()
        logger.info("=" * 50)
        logger.info("📊 Estatísticas finais:")
        logger.info(f"  Processadas : {s['processed']}")
        logger.info(f"  Ignoradas   : {s['skipped']}")
        logger.info(f"  Erros       : {s['errors']}")
        logger.info(f"  BloomFilter : {s['bloom_size']} URLs")
        logger.info(f"  Fetcher     : {s['fetcher']}")
        logger.info(f"  MongoDB     : {s['mongo']}")
        logger.info(f"  Queue       : {s['queue']}")
        logger.info("=" * 50)

    def stats(self) -> dict:
        """
        Retorna estatísticas do crawler.
        Se chamado após shutdown, retorna o cache salvo antes do fechamento.
        """
        if self._cached_stats is not None:
            return self._cached_stats

        return {
            "processed": self._processed,
            "skipped": self._skipped,
            "errors": self._errors,
            "bloom_size": len(self.bloom),
            "fetcher": self.fetcher.stats(),
            "mongo": self.mongo.stats(),
            "queue": self.queue.stats(),
        }
