import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.storage.elastic_client import ElasticStorage
from src.crawler.fetcher import FetchResult
from src.crawler.parser import ParseResult

# ── Instanciar storage ─────────────────────────────────────
storage = ElasticStorage()

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

# ── Indexar página ─────────────────────────────────────────
print("Indexando página de teste...")
indexed = storage.index_page(fetch_result, parse_result, depth=0)
print(f"  Indexado: {indexed}")

# ── Aguardar indexação ─────────────────────────────────────
import time
time.sleep(1)

# ── Verificar se existe ────────────────────────────────────
print("\nVerificando se URL existe...")
exists = storage.url_exists("https://example.com")
print(f"  Existe: {exists}")

# ── Buscar página ──────────────────────────────────────────
print("\nBuscando por 'example'...")
results = storage.search("example", size=5)
for r in results:
    print(f"  [{r['_score']:.2f}] {r['title']} → {r['url']}")

# ── Estatísticas ───────────────────────────────────────────
print("\nEstatísticas:")
for k, v in storage.stats().items():
    print(f"  {k}: {v}")

storage.close()
