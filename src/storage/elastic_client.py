from elasticsearch import Elasticsearch, helpers
from loguru import logger

from src.config import get_settings
from src.crawler.parser import ParseResult
from src.crawler.fetcher import FetchResult


class ElasticStorage:
    """
    Responsável por indexar páginas crawleadas no ElasticSearch.
    """

    # ── Mapeamento do índice ──────────────────────────────────
    INDEX_MAPPING = {
        "mappings": {
            "properties": {
                "url":          {"type": "keyword"},
                "final_url":    {"type": "keyword"},
                "domain":       {"type": "keyword"},
                "depth":        {"type": "integer"},
                "title":        {"type": "text", "analyzer": "standard"},
                "description":  {"type": "text", "analyzer": "standard"},
                "body_text":    {"type": "text", "analyzer": "standard"},
                "lang":         {"type": "keyword"},
                "word_count":   {"type": "integer"},
                "headings":     {"type": "object", "enabled": False},
                "links":        {"type": "keyword"},
                "links_count":  {"type": "integer"},
                "images":       {"type": "keyword"},
                "status_code":  {"type": "integer"},
                "content_type": {"type": "keyword"},
                "elapsed_ms":   {"type": "float"},
                "crawled_at":   {"type": "date", "format": "strict_date_optional_time"},
            }
        },
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        }
    }

    def __init__(self):
        settings = get_settings()

        self.client = Elasticsearch(settings.es_uri)
        self.index = settings.es_index

        # Criar índice se não existir
        self._create_index()

        logger.info(
            f"ElasticSearch conectado | "
            f"index={self.index} | "
            f"uri={settings.es_uri}"
        )

    # Índice

    def _create_index(self) -> None:
        """Cria o índice com mapeamento se não existir."""
        if not self.client.indices.exists(index=self.index):
            self.client.indices.create(
                index=self.index,
                body=self.INDEX_MAPPING,
            )
            logger.info(f"Índice criado: {self.index}")
        else:
            logger.debug(f"Índice já existe: {self.index}")

    # Indexar página

    def index_page(
        self,
        fetch_result: FetchResult,
        parse_result: ParseResult,
        depth: int = 0,
    ) -> bool:
        """
        Indexa uma página no ElasticSearch.

        Returns:
            True  → indexado com sucesso
            False → erro ao indexar
        """
        from urllib.parse import urlparse
        domain = urlparse(fetch_result.url).netloc

        document = {
            # Identificação
            "url":          fetch_result.url,
            "final_url":    fetch_result.final_url,
            "domain":       domain,
            "depth":        depth,

            # Conteúdo 
            "title":        parse_result.title,
            "description":  parse_result.description,
            "body_text":    parse_result.body_text,
            "lang":         parse_result.lang,
            "word_count":   parse_result.word_count,
            "headings":     parse_result.headings,

            # Links e mídia
            "links":        parse_result.links,
            "links_count":  len(parse_result.links),
            "images":       parse_result.images,

            # Metadados HTTP
            "status_code":  fetch_result.status_code,
            "content_type": fetch_result.content_type,
            "elapsed_ms":   fetch_result.elapsed_ms,

            # Timestamp
            "crawled_at":   fetch_result.crawled_at,
        }

        try:
            self.client.index(
                index=self.index,
                id=fetch_result.url,   
                document=document,
            )
            logger.debug(f"✅ Página indexada no ES: {fetch_result.url}")
            return True

        except Exception as e:
            logger.error(f"❌ Erro ao indexar no ES: {fetch_result.url} | {e}")
            return False

    # Indexação em lote 

    def bulk_index(self, documents: list[dict]) -> tuple[int, int]:
        """
        Indexa múltiplos documentos de uma vez.

        Returns:
            Tuple (sucesso, falhas)
        """
        actions = [
            {
                "_index": self.index,
                "_id": doc["url"],
                "_source": doc,
            }
            for doc in documents
        ]

        success, errors = helpers.bulk(
            self.client,
            actions,
            raise_on_error=False,
        )

        logger.info(f"Bulk index: {success} sucesso, {len(errors)} falhas")
        return success, len(errors)

    # Busca 

    def search(
        self,
        query: str,
        domain: str | None = None,
        lang: str | None = None,
        size: int = 10,
        from_: int = 0,              
    ) -> tuple[list[dict], int]:    
        """
        Busca full-text nas páginas indexadas.

        Args:
            query:  texto a buscar
            domain: filtrar por domínio 
            lang:   filtrar por idioma 
            size:   número máximo de resultados por página
            from_:  offset para paginação
        """
        must = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "description^2", "body_text"],
                    "type": "best_fields",
                }
            }
        ]

        filters = []
        if domain:
            filters.append({"term": {"domain": domain}})
        if lang:
            filters.append({"term": {"lang": lang}})

        body = {
            "query": {
                "bool": {
                    "must": must,
                    "filter": filters,
                }
            },
            "_source": ["url", "title", "description", "domain", "lang", "crawled_at"],
            "from": from_,
            "size": size,
            "track_total_hits": True,   # garante contagem exata acima de 10k
        }

        try:
            response = self.client.search(index=self.index, body=body)
            hits     = response["hits"]["hits"]
            total    = response["hits"]["total"]["value"]

            results = [
                {**hit["_source"], "_score": hit["_score"]}
                for hit in hits
            ]
            return results, total

        except Exception as e:
            logger.error(f"Erro na busca ES: {e}")
            return [], 0


    def url_exists(self, url: str) -> bool:
        """Verifica se uma URL já foi indexada."""
        return self.client.exists(index=self.index, id=url)

    # Estatísticas

    def stats(self) -> dict:
        """Retorna estatísticas do índice."""
        try:
            count = self.client.count(index=self.index)
            info = self.client.indices.stats(index=self.index)
            store = info["indices"][self.index]["total"]["store"]

            return {
                "total_documents": count["count"],
                "index_size_bytes": store["size_in_bytes"],
                "index_size_mb": round(store["size_in_bytes"] / 1024 / 1024, 2),
            }
        except Exception as e:
            logger.error(f"Erro ao buscar stats do ES: {e}")
            return {}

    def close(self) -> None:
        """Fecha a conexão com o ElasticSearch."""
        self.client.close()
        logger.info("ElasticSearch desconectado")
