import httpx
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger

from src.config import get_settings
from src.crawler.politeness import PolitenessPolicy


@dataclass
class FetchResult:
    """Resultado de uma requisição HTTP."""
    url: str
    status_code: int
    html: str
    content_type: str
    crawled_at: str
    elapsed_ms: float
    error: str | None = None
    success: bool = True
    final_url: str = ""        
    headers: dict = field(default_factory=dict)


class Fetcher:
    """
    Responsável por baixar páginas de forma assíncrona.
    """

    ALLOWED_CONTENT_TYPES = (
        "text/html",
        "application/xhtml+xml",
    )

    def __init__(self, politeness: PolitenessPolicy | None = None):
        settings = get_settings()

        self.timeout = settings.request_timeout
        self.user_agent = settings.user_agent
        self.politeness = politeness or PolitenessPolicy(
            rate_limit_delay=settings.rate_limit_delay,
            respect_robots_txt=settings.respect_robots_txt,
            user_agent=settings.user_agent,
        )

        # Estatísticas
        self._fetched = 0
        self._failed = 0
        self._skipped = 0

    # Cliente HTTP

    def _build_client(self) -> httpx.AsyncClient:
        """Cria o cliente HTTP com configurações padrão."""
        return httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            headers={"User-Agent": self.user_agent},
            follow_redirects=True,
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
            ),
        )

    # Fetch principal

    async def fetch(self, url: str, retries: int = 3) -> FetchResult:
        """
        Baixa uma URL respeitando politeness policy.

        Args:
            url:     URL a ser baixada
            retries: número de tentativas em caso de falha
        """
        # Verificar politeness
        can_crawl = await self.politeness.can_crawl(url)
        if not can_crawl:
            self._skipped += 1
            logger.info(f"⛔ Bloqueado pelo robots.txt: {url}")
            return FetchResult(
                url=url,
                status_code=0,
                html="",
                content_type="",
                crawled_at=datetime.utcnow().isoformat(),
                elapsed_ms=0,
                error="Bloqueado pelo robots.txt",
                success=False,
                final_url=url,
            )

        # Tentar download com retry 
        last_error = None

        for attempt in range(1, retries + 1):
            try:
                result = await self._do_fetch(url)

                if result.success:
                    self._fetched += 1
                    logger.info(
                        f"✅ [{result.status_code}] {url} "
                        f"({result.elapsed_ms:.0f}ms)"
                    )
                else:
                    self._failed += 1

                return result

            except Exception as e:
                last_error = e
                wait = 2 ** attempt  
                logger.warning(
                    f"⚠️  Tentativa {attempt}/{retries} falhou para {url}: {e} "
                    f"— aguardando {wait}s"
                )
                await asyncio.sleep(wait)

        # Todas as tentativas falharam 
        self._failed += 1
        logger.error(f"❌ Falha total após {retries} tentativas: {url}")

        return FetchResult(
            url=url,
            status_code=0,
            html="",
            content_type="",
            crawled_at=datetime.utcnow().isoformat(),
            elapsed_ms=0,
            error=str(last_error),
            success=False,
            final_url=url,
        )

    async def _do_fetch(self, url: str) -> FetchResult:
        """Executa a requisição HTTP de fato."""
        import time

        start = time.monotonic()

        async with self._build_client() as client:
            response = await client.get(url)

        elapsed_ms = (time.monotonic() - start) * 1000
        content_type = response.headers.get("content-type", "")

        # Filtrar por content-type
        is_html = any(ct in content_type for ct in self.ALLOWED_CONTENT_TYPES)

        if not is_html:
            return FetchResult(
                url=url,
                status_code=response.status_code,
                html="",
                content_type=content_type,
                crawled_at=datetime.utcnow().isoformat(),
                elapsed_ms=elapsed_ms,
                error=f"Content-type não suportado: {content_type}",
                success=False,
                final_url=str(response.url),
                headers=dict(response.headers),
            )

        return FetchResult(
            url=url,
            status_code=response.status_code,
            html=response.text,
            content_type=content_type,
            crawled_at=datetime.utcnow().isoformat(),
            elapsed_ms=elapsed_ms,
            error=None,
            success=response.status_code < 400,
            final_url=str(response.url),
            headers=dict(response.headers),
        )

    # Fetch em lote

    async def fetch_many(self, urls: list[str]) -> list[FetchResult]:
        """Baixa múltiplas URLs de forma concorrente."""
        tasks = [self.fetch(url) for url in urls]
        return await asyncio.gather(*tasks)

    # Estatísticas

    def stats(self) -> dict:
        total = self._fetched + self._failed + self._skipped
        return {
            "fetched": self._fetched,
            "failed": self._failed,
            "skipped": self._skipped,
            "total": total,
            "success_rate": (
                f"{(self._fetched / total * 100):.1f}%"
                if total > 0 else "N/A"
            ),
        }
