import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.storage.mongo_client import MongoStorage
from src.crawler.fetcher import FetchResult
from src.crawler.parser import ParseResult

# ── Instanciar storage ─────────────────────────────────────
storage = MongoStorage()

# ── Dados de teste ─────────────────────────────────────────
fetch_result = FetchResult(
    url="https://example.com",
    final_url="https://example.com",
    status_code=200,
    html="<html></html>",
    content_type="text/html",
    crawled_at="2024-01-01T00:00:00",
    elapsed_ms=350.0,
)

parse_result = ParseResult(
    url="https://example.com",
    title="Example Domain",
    description="This domain is for use in examples.",
    body_text="Example Domain. This domain is for use in illustrative examples.",
    links=["https://www.iana.org/domains/example"],
    images=[],
    lang="en",
    word_count=42,
    headings={"h1": ["Example Domain"]},
)

# ── Salvar página ──────────────────────────────────────────
print("Salvando página de teste...")
saved = storage.save_page(fetch_result, parse_result, depth=0)
print(f"  Salvo: {saved}")

# ── Verificar se existe ────────────────────────────────────
print("\nVerificando se URL existe...")
exists = storage.url_exists("https://example.com")
print(f"  Existe: {exists}")

# ── Buscar página ──────────────────────────────────────────
print("\nBuscando página...")
page = storage.get_page("https://example.com")
if page:
    print(f"  Título : {page['title']}")
    print(f"  Domínio: {page['domain']}")
    print(f"  Palavras: {page['word_count']}")

# ── Estatísticas ───────────────────────────────────────────
print("\nEstatísticas:")
for k, v in storage.stats().items():
    print(f"  {k}: {v}")

storage.close()
