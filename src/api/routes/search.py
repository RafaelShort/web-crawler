from math import ceil

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from loguru import logger

from src.storage.elastic_client import ElasticStorage
from src.storage.mongo_client import MongoStorage

router = APIRouter()


# Schemas

class SearchResult(BaseModel):
    url: str
    title: str
    description: str
    domain: str
    lang: str
    score: float
    crawled_at: str


class SearchResponse(BaseModel):
    query: str
    total: int          # total de hits no ES
    page: int           # página atual
    size: int           # resultados por página
    total_pages: int    # total de páginas
    results: list[SearchResult]


# Endpoints

@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Busca full-text nas páginas crawleadas",
)
async def search(
    q: str = Query(..., min_length=2, description="Termo de busca"),
    domain: str | None = Query(None, description="Filtrar por domínio"),
    lang: str | None = Query(None, description="Filtrar por idioma (ex: pt-BR, en)"),
    size: int = Query(10, ge=1, le=50, description="Resultados por página"),
    page: int = Query(1, ge=1, description="Número da página"),
):
    """
    Busca full-text com paginação nas páginas crawleadas.

    - **q**: termo de busca (mínimo 2 caracteres)
    - **domain**: filtrar por domínio
    - **lang**: filtrar por idioma 
    - **size**: resultados por página (1-50)
    - **page**: número da página (começa em 1)
    """
    try:
        from_ = (page - 1) * size

        elastic = ElasticStorage()
        raw_results, total = elastic.search(
            query=q,
            domain=domain,
            lang=lang,
            size=size,
            from_=from_,
        )
        elastic.close()

        results = [
            SearchResult(
                url=r.get("url", ""),
                title=r.get("title", ""),
                description=r.get("description", ""),
                domain=r.get("domain", ""),
                lang=r.get("lang", ""),
                score=round(r.get("_score", 0.0), 4),
                crawled_at=r.get("crawled_at", ""),
            )
            for r in raw_results
        ]

        return SearchResponse(
            query=q,
            total=total,
            page=page,
            size=size,
            total_pages=ceil(total / size) if total > 0 else 1,
            results=results,
        )

    except Exception as e:
        logger.error(f"Erro na busca: {e}")
        raise HTTPException(status_code=500, detail=f"Erro na busca: {str(e)}")


@router.get(
    "/pages/{domain:path}",
    summary="Listar páginas de um domínio",
)
async def list_pages(
    domain: str,
    limit: int = Query(10, ge=1, le=100),
):
    """
    Lista as páginas crawleadas de um domínio específico.

    - **domain**: domínio a consultar
    - **limit**: número máximo de resultados (1-100)
    """
    try:
        mongo = MongoStorage()
        pages = mongo.get_pages_by_domain(domain=domain, limit=limit)
        mongo.close()

        return {
            "domain": domain,
            "total": len(pages),
            "pages": pages,
        }

    except Exception as e:
        logger.error(f"Erro ao listar páginas: {e}")
        raise HTTPException(status_code=500, detail=str(e))
