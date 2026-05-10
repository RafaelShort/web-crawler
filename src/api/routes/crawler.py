import asyncio
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, HttpUrl
from loguru import logger

from src.crawler.engine import CrawlerEngine

router = APIRouter()

# Estado global do crawler 
_engine: CrawlerEngine | None = None
_task: asyncio.Task | None = None


# Schemas

class StartRequest(BaseModel):
    seed_urls: list[HttpUrl]
    max_depth: int = 3
    max_workers: int = 5

    model_config = {"json_schema_extra": {
        "example": {
            "seed_urls": ["https://example.com"],
            "max_depth": 2,
            "max_workers": 3,
        }
    }}


class StartResponse(BaseModel):
    message: str
    seed_urls: list[str]


class StatusResponse(BaseModel):
    running: bool
    stats: dict | None = None


# Helpers

async def _run_crawler(engine: CrawlerEngine, seed_urls: list[str]):
    """Executa o crawler em background."""
    try:
        await engine.start(seed_urls)
    except Exception as e:
        logger.error(f"Erro no crawler: {e}")


# Endpoints

@router.post(
    "/crawler/start",
    response_model=StartResponse,
    summary="Iniciar o crawler",
)
async def start_crawler(
    request: StartRequest,
    background_tasks: BackgroundTasks,
):
    """
    Inicia o crawler com as URLs semente fornecidas.

    - **seed_urls**: lista de URLs para iniciar o crawling
    - **max_depth**: profundidade máxima de crawling (padrão: 3)
    - **max_workers**: número de workers paralelos (padrão: 5)
    """
    global _engine, _task

    if _task and not _task.done():
        raise HTTPException(
            status_code=409,
            detail="Crawler já está em execução. Pare-o antes de iniciar novamente.",
        )

    seed_urls = [str(url) for url in request.seed_urls]

    _engine = CrawlerEngine()
    loop = asyncio.get_event_loop()
    _task = loop.create_task(_run_crawler(_engine, seed_urls))

    logger.info(f"Crawler iniciado via API com {len(seed_urls)} seeds")

    return StartResponse(
        message="Crawler iniciado com sucesso",
        seed_urls=seed_urls,
    )


@router.post(
    "/crawler/stop",
    summary="Parar o crawler",
)
async def stop_crawler():
    """Para o crawler em execução."""
    global _engine, _task

    if not _engine:
        raise HTTPException(
            status_code=404,
            detail="Nenhum crawler em execução.",
        )

    await _engine.shutdown()
    logger.info("Crawler parado via API")

    return {"message": "Crawler parado com sucesso"}


@router.get(
    "/crawler/status",
    response_model=StatusResponse,
    summary="Status do crawler",
)
async def crawler_status():
    """Retorna o status atual do crawler e suas estatísticas."""
    global _engine, _task

    if not _engine:
        return StatusResponse(running=False, stats=None)

    is_running = _task is not None and not _task.done()

    return StatusResponse(
        running=is_running,
        stats=_engine.stats(),
    )
