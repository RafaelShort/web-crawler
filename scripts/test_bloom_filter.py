import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.crawler.bloom_filter import BloomFilter

bf = BloomFilter(capacity=1000, error_rate=0.01)

# Adicionar URLs
bf.add("https://example.com")
bf.add("https://python.org")
bf.add("https://github.com")

# Testar URLs conhecidas
print("Testes de URLs conhecidas:")
print(f"  example.com -> {'ja vista' if 'https://example.com' in bf else 'nova'}")
print(f"  python.org  -> {'ja vista' if 'https://python.org' in bf else 'nova'}")

print()

# Testar URLs novas
print("Testes de URLs novas:")
print(f"  google.com  -> {'ja vista' if 'https://google.com' in bf else 'nova'}")
print(f"  ford.com    -> {'ja vista' if 'https://ford.com' in bf else 'nova'}")

print()

# Estatísticas
print("Estatisticas:")
for k, v in bf.stats().items():
    print(f"  {k}: {v}")
