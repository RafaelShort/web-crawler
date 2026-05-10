from datetime import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError
from loguru import logger

from src.config import get_settings
from src.crawler.parser import ParseResult
from src.crawler.fetcher import FetchResult


class MongoStorage:
    """
    Responsável por persistir os dados crawleados no MongoDB.
    """

    def __init__(self):
        settings = get_settings()

        self.client = MongoClient(settings.mongo_uri)
        self.db = self.client[settings.mongo_db]

        # Coleções
        self.pages: Collection = self.db["pages"]
        self.errors: Collection = self.db["errors"]
        self.domains: Collection = self.db["domains"]

        # Criar índices
        self._create_indexes()

        logger.info(
            f"MongoDB conectado | "
            f"db={settings.mongo_db} | "
            f"uri={settings.mongo_uri}"
        )

    # Índices

    def _create_indexes(self) -> None:
        """Cria índices para otimizar consultas."""

        # pages: URL única + busca por domínio e data
        self.pages.create_index("url", unique=True)
        self.pages.create_index("domain")
        self.pages.create_index([("crawled_at", DESCENDING)])
        self.pages.create_index("depth")

        # errors: URL única + data
        self.errors.create_index("url", unique=True)
        self.errors.create_index([("failed_at", DESCENDING)])

        # domains: nome único
        self.domains.create_index("domain", unique=True)

        logger.debug("Índices MongoDB criados com sucesso")

    # Salvar página

    def save_page(
        self,
        fetch_result: FetchResult,
        parse_result: ParseResult,
        depth: int = 0,
    ) -> bool:
        """
        Salva uma página crawleada no MongoDB.
        """
        from urllib.parse import urlparse
        domain = urlparse(fetch_result.url).netloc

        document = {
            # Identificação
            "url": fetch_result.url,
            "final_url": fetch_result.final_url,
            "domain": domain,
            "depth": depth,

            # Conteúdo
            "title": parse_result.title,
            "description": parse_result.description,
            "body_text": parse_result.body_text,
            "lang": parse_result.lang,
            "word_count": parse_result.word_count,
            "headings": parse_result.headings,

            # Links e mídia
            "links": parse_result.links,
            "links_count": len(parse_result.links),
            "images": parse_result.images,

            # Metadados HTTP
            "status_code": fetch_result.status_code,
            "content_type": fetch_result.content_type,
            "elapsed_ms": fetch_result.elapsed_ms,

            # Timestamps
            "crawled_at": fetch_result.crawled_at,
            "created_at": datetime.utcnow().isoformat(),
        }

        try:
            self.pages.insert_one(document)
            self._update_domain_stats(domain)
            logger.debug(f"✅ Página salva no MongoDB: {fetch_result.url}")
            return True

        except DuplicateKeyError:
            logger.debug(f"⚠️  Página já existe no MongoDB: {fetch_result.url}")
            return False

    # Salvar erro

    def save_error(self, fetch_result: FetchResult) -> None:
        """Salva uma página que falhou no crawling."""
        from urllib.parse import urlparse
        domain = urlparse(fetch_result.url).netloc

        document = {
            "url": fetch_result.url,
            "domain": domain,
            "error": fetch_result.error,
            "status_code": fetch_result.status_code,
            "failed_at": datetime.utcnow().isoformat(),
        }

        try:
            self.errors.update_one(
                {"url": fetch_result.url},
                {"$set": document},
                upsert=True,
            )
            logger.debug(f"❌ Erro salvo no MongoDB: {fetch_result.url}")

        except Exception as e:
            logger.error(f"Erro ao salvar falha no MongoDB: {e}")

    # Estatísticas por domínio

    def _update_domain_stats(self, domain: str) -> None:
        """Atualiza contador de páginas por domínio."""
        self.domains.update_one(
            {"domain": domain},
            {
                "$inc": {"pages_crawled": 1},
                "$set": {"last_crawled_at": datetime.utcnow().isoformat()},
                "$setOnInsert": {"first_crawled_at": datetime.utcnow().isoformat()},
            },
            upsert=True,
        )

    # Consultas

    def url_exists(self, url: str) -> bool:
        """Verifica se uma URL já foi crawleada."""
        return self.pages.count_documents({"url": url}, limit=1) > 0

    def get_page(self, url: str) -> dict | None:
        """Retorna uma página pelo URL."""
        return self.pages.find_one({"url": url}, {"_id": 0})

    def get_pages_by_domain(self, domain: str, limit: int = 10) -> list[dict]:
        """Retorna páginas de um domínio."""
        cursor = self.pages.find(
            {"domain": domain},
            {"_id": 0, "url": 1, "title": 1, "crawled_at": 1}
        ).sort("crawled_at", DESCENDING).limit(limit)
        return list(cursor)

    # Estatísticas gerais

    def stats(self) -> dict:
        """Retorna estatísticas gerais do banco."""
        return {
            "total_pages": self.pages.count_documents({}),
            "total_errors": self.errors.count_documents({}),
            "total_domains": self.domains.count_documents({}),
        }

    def close(self) -> None:
        """Fecha a conexão com o MongoDB."""
        self.client.close()
        logger.info("MongoDB desconectado")
