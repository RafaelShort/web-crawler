from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.api.routes import crawler, search, health, ui


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 API iniciando...")
    yield
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

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers API ───────────────────────────────────────────────────────────────
app.include_router(health.router,  prefix="/api/v1", tags=["Health"])
app.include_router(crawler.router, prefix="/api/v1", tags=["Crawler"])
app.include_router(search.router,  prefix="/api/v1", tags=["Search"])

# ── Router UI ─────────────────────────────────────────────────────────────────
app.include_router(ui.router)  # ← sem prefixo, captura o "/"
