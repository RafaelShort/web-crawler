from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.api.routes import crawler, search, health, ui
from src.storage.elastic_client import ElasticStorage
from src.storage.mongo_client import MongoStorage


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("API iniciando...")
    app.state.elastic = ElasticStorage()
    app.state.mongo = MongoStorage()
    yield
    app.state.elastic.close()
    app.state.mongo.close()
    logger.info("🛑 API encerrando...")


app = FastAPI(
    title="Web Crawler API",
    description="""
API REST para controle e consulta do Web Crawler.

## Funcionalidades
- **Crawler** → iniciar, parar e monitorar o crawler
- **Search**  → busca full-text nas páginas crawleadas
- **Health**  → status dos serviços
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router,  prefix="/api/v1", tags=["Health"])
app.include_router(crawler.router, prefix="/api/v1", tags=["Crawler"])
app.include_router(search.router,  prefix="/api/v1", tags=["Search"])

app.include_router(ui.router)
