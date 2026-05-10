from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # MongoDB
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "web_crawler"

    # ElasticSearch
    es_uri: str = "http://localhost:9200"
    es_index: str = "crawled_pages"

    # RabbitMQ 
    rabbitmq_uri: str = "amqp://guest:guest@localhost:5672/"
    rabbitmq_queue: str = "url_queue"

    # Crawler
    max_workers: int = 5
    max_depth: int = 3
    request_timeout: int = 30
    rate_limit_delay: float = 1.0
    respect_robots_txt: bool = True
    user_agent: str = "WebCrawler/1.0 (+https://github.com/seu-usuario/web-crawler)"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
