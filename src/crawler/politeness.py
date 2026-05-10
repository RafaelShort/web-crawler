import asyncio
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from collections import defaultdict
import httpx
from loguru import logger


class PolitenessPolicy:
    """
    Garante que o crawler siga as seguintes regras:

    1. Respeita robots.txt  → não acessa rotas proibidas
    2. Rate limiting        → aguarda entre requisições ao mesmo domínio
    3. Cache de robots.txt  → evita baixar o mesmo arquivo repetidamente
    """

    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        respect_robots_txt: bool = True,
        user_agent: str = "WebCrawler/1.0",
    ):
        self.rate_limit_delay = rate_limit_delay
        self.respect_robots_txt = respect_robots_txt
        self.user_agent = user_agent

        # Cache: domain → RobotFileParser
        self._robots_cache: dict[str, RobotFileParser | None] = {}

        # Último acesso por domínio: domain → timestamp
        self._last_access: dict[str, float] = defaultdict(float)

        # Lock por domínio para concorrência 
        self._domain_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    # Utilitários

    @staticmethod
    def _get_domain(url: str) -> str:
        """Extrai o domínio de uma URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def _get_robots_url(url: str) -> str:
        """Retorna a URL do robots.txt de um domínio."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    # robots.txt

    async def _fetch_robots(self, url: str) -> RobotFileParser | None:
        """Baixa e parseia o robots.txt de um domínio."""
        robots_url = self._get_robots_url(url)
        parser = RobotFileParser()
        parser.set_url(robots_url)

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    robots_url,
                    headers={"User-Agent": self.user_agent},
                    follow_redirects=True,
                )
                if response.status_code == 200:
                    parser.parse(response.text.splitlines())
                    logger.debug(f"robots.txt carregado: {robots_url}")
                else:
                    logger.debug(f"robots.txt não encontrado ({response.status_code}): {robots_url}")
                    return None
        except Exception as e:
            logger.warning(f"Erro ao buscar robots.txt de {robots_url}: {e}")
            return None

        return parser

    async def _get_robots_parser(self, url: str) -> RobotFileParser | None:
        """Retorna o parser de robots.txt com cache."""
        domain = self._get_domain(url)

        if domain not in self._robots_cache:
            self._robots_cache[domain] = await self._fetch_robots(url)

        return self._robots_cache[domain]

    async def is_allowed(self, url: str) -> bool:
        """
        Verifica se a URL pode ser crawleada.

        Returns:
            True  → URL permitida
            False → URL bloqueada pelo robots.txt
        """
        if not self.respect_robots_txt:
            return True

        parser = await self._get_robots_parser(url)

        if parser is None:
            return True

        allowed = parser.can_fetch(self.user_agent, url)

        if not allowed:
            logger.debug(f"Bloqueado pelo robots.txt: {url}")

        return allowed

    # Rate Limiting

    async def wait_if_needed(self, url: str) -> None:
        """
        Aguarda o tempo necessário antes de fazer uma requisição
        ao domínio, respeitando o rate limit configurado.
        """
        domain = self._get_domain(url)

        async with self._domain_locks[domain]:
            now = time.monotonic()
            elapsed = now - self._last_access[domain]
            wait_time = self.rate_limit_delay - elapsed

            if wait_time > 0:
                logger.debug(f"Rate limit: aguardando {wait_time:.2f}s para {domain}")
                await asyncio.sleep(wait_time)

            self._last_access[domain] = time.monotonic()

    # Interface principal

    async def can_crawl(self, url: str) -> bool:
        """
        Verifica se a URL pode ser crawleada E aplica rate limiting.

        Uso:
            if await policy.can_crawl(url):
                # fetch da página
        """
        allowed = await self.is_allowed(url)

        if allowed:
            await self.wait_if_needed(url)

        return allowed

    def stats(self) -> dict:
        """Retorna estatísticas da política."""
        return {
            "domains_visited": len(self._last_access),
            "robots_cached": len(self._robots_cache),
            "rate_limit_delay": self.rate_limit_delay,
            "respect_robots_txt": self.respect_robots_txt,
        }
