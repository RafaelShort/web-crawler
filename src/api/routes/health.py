from fastapi import APIRouter
from pymongo import MongoClient
from elasticsearch import Elasticsearch
import aio_pika
from loguru import logger

from src.config import get_settings

router = APIRouter()


@router.get("/health", summary="Status de todos os serviços")
async def health_check():
    """
    Verifica o status de todos os serviços:
    - MongoDB
    - ElasticSearch
    - RabbitMQ
    """
    settings = get_settings()
    services = {}

    # MongoDB
    try:
        client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=2000)
        client.server_info()
        client.close()
        services["mongodb"] = {"status": "ok", "uri": settings.mongo_uri}
    except Exception as e:
        logger.warning(f"MongoDB health check falhou: {e}")
        services["mongodb"] = {"status": "error", "detail": str(e)}

    # ElasticSearch
    try:
        es = Elasticsearch(settings.es_uri)
        info = es.info()
        es.close()
        services["elasticsearch"] = {
            "status": "ok",
            "version": info["version"]["number"],
            "uri": settings.es_uri,
        }
    except Exception as e:
        logger.warning(f"ElasticSearch health check falhou: {e}")
        services["elasticsearch"] = {"status": "error", "detail": str(e)}

    # RabbitMQ
    try:
        connection = await aio_pika.connect_robust(
            settings.rabbitmq_uri,
            timeout=2,
        )
        await connection.close()
        services["rabbitmq"] = {"status": "ok", "uri": settings.rabbitmq_uri}
    except Exception as e:
        logger.warning(f"RabbitMQ health check falhou: {e}")
        services["rabbitmq"] = {"status": "error", "detail": str(e)}

    # Status geral
    all_ok = all(s["status"] == "ok" for s in services.values())

    return {
        "status": "ok" if all_ok else "degraded",
        "services": services,
    }
