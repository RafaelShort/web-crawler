from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from loguru import logger


@dataclass
class ParseResult:
    """Resultado do parsing de uma página HTML."""
    url: str
    title: str
    description: str
    body_text: str
    links: list[str]
    images: list[str]
    lang: str
    word_count: int
    headings: dict[str, list[str]] = field(default_factory=dict)


class Parser:
    """
    Responsável por extrair informações de páginas HTML.
    """

    # Extensões que devem ser ignoradas
    IGNORED_EXTENSIONS = (
        ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg",
        ".mp4", ".mp3", ".zip", ".rar", ".exe", ".dmg",
        ".css", ".js", ".ico", ".xml", ".json",
    )

    # Esquemas válidos
    VALID_SCHEMES = ("http", "https")

    def parse(self, html: str, base_url: str) -> ParseResult:
        """
        Parseia o HTML e extrai informações relevantes.

        Args:
            html:     conteúdo HTML da página
            base_url: URL base para resolução de links relativos
        """
        soup = BeautifulSoup(html, "lxml")

        return ParseResult(
            url=base_url,
            title=self._extract_title(soup),
            description=self._extract_description(soup),
            body_text=self._extract_body_text(soup),
            links=self._extract_links(soup, base_url),
            images=self._extract_images(soup, base_url),
            lang=self._extract_lang(soup),
            word_count=self._count_words(soup),
            headings=self._extract_headings(soup),
        )

    # Extratores

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extrai o título da página."""
        # Tenta <title>
        if soup.title and soup.title.string:
            return soup.title.string.strip()

        # Fallback para <h1>
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        return ""

    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extrai a descrição da página com fallbacks progressivos."""

        # 1. <meta name="description">
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content", "").strip():
            return meta["content"].strip()

        # 2. <meta property="og:description">
        og_meta = soup.find("meta", attrs={"property": "og:description"})
        if og_meta and og_meta.get("content", "").strip():
            return og_meta["content"].strip()

        # 3. <meta name="twitter:description">
        tw_meta = soup.find("meta", attrs={"name": "twitter:description"})
        if tw_meta and tw_meta.get("content", "").strip():
            return tw_meta["content"].strip()

        # 4. Primeiro <p> com conteúdo relevante (mínimo 40 chars)
        for tag in soup.find_all("p"):
            text = tag.get_text(separator=" ", strip=True)
            if len(text) >= 40:
                return text[:300]

        # 5. Primeiro heading + texto seguinte
        for level in ["h1", "h2"]:
            heading = soup.find(level)
            if heading:
                sibling = heading.find_next_sibling()
                if sibling:
                    text = sibling.get_text(separator=" ", strip=True)
                    if len(text) >= 20:
                        return text[:300]

        # 6. Últmo recurso: primeiros 300 chars do body_text
        for tag in soup(["script", "style", "noscript", "nav", "footer"]):
            tag.decompose()
        body = soup.find("body")
        if body:
            text = " ".join(body.get_text(separator=" ").split())
            if text:
                return text[:300]

        return ""


    def _extract_body_text(self, soup: BeautifulSoup) -> str:
        """Extrai o texto limpo do body, removendo scripts e estilos."""
        # Remover tags desnecessárias
        for tag in soup(["script", "style", "noscript", "nav", "footer", "iframe"]):
            tag.decompose()

        body = soup.find("body")
        if body:
            return " ".join(body.get_text(separator=" ").split())

        return " ".join(soup.get_text(separator=" ").split())

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Extrai e normaliza todos os links da página."""
        links = set()

        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()

            # Ignorar links vazios, âncoras e javascript
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue

            # Resolver URL relativa
            absolute_url = urljoin(base_url, href)

            # Validar URL
            if self._is_valid_url(absolute_url):
                links.add(self._normalize_url(absolute_url))

        return sorted(links)

    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Extrai URLs de imagens da página."""
        images = set()

        for tag in soup.find_all("img", src=True):
            src = tag["src"].strip()
            if src:
                absolute_url = urljoin(base_url, src)
                parsed = urlparse(absolute_url)
                if parsed.scheme in self.VALID_SCHEMES:
                    images.add(absolute_url)

        return sorted(images)

    def _extract_lang(self, soup: BeautifulSoup) -> str:
        """Extrai o idioma da página."""
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            return html_tag["lang"].strip()
        return ""

    def _extract_headings(self, soup: BeautifulSoup) -> dict[str, list[str]]:
        """Extrai todos os headings h1, h2, h3."""
        headings = {}

        for level in ["h1", "h2", "h3"]:
            tags = soup.find_all(level)
            if tags:
                headings[level] = [
                    tag.get_text(strip=True)
                    for tag in tags
                    if tag.get_text(strip=True)
                ]

        return headings

    def _count_words(self, soup: BeautifulSoup) -> int:
        """Conta o número de palavras no body."""
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
        return len(text.split())

    # Validação e normalização

    def _is_valid_url(self, url: str) -> bool:
        """Verifica se a URL é válida para crawling."""
        try:
            parsed = urlparse(url)

            # Verificar esquema
            if parsed.scheme not in self.VALID_SCHEMES:
                return False

            # Verificar host
            if not parsed.netloc:
                return False

            # Verificar extensão
            path = parsed.path.lower()
            if any(path.endswith(ext) for ext in self.IGNORED_EXTENSIONS):
                return False

            return True

        except Exception:
            return False

    def _normalize_url(self, url: str) -> str:
        """Normaliza a URL removendo fragmentos e trailing slashes."""
        parsed = urlparse(url)

        # Remover fragmento (#section)
        normalized = parsed._replace(fragment="")

        url_str = normalized.geturl()

        # Remover trailing slash (exceto raiz)
        if url_str.endswith("/") and url_str.count("/") > 2:
            url_str = url_str.rstrip("/")

        return url_str
