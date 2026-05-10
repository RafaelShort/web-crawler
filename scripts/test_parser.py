import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.crawler.parser import Parser

HTML_SAMPLE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <title>Página de Teste</title>
    <meta name="description" content="Esta é uma página de teste do web crawler.">
</head>
<body>
    <h1>Título Principal</h1>
    <h2>Subtítulo 1</h2>
    <p>Este é um parágrafo de teste com algumas palavras.</p>
    <h2>Subtítulo 2</h2>
    <p>Outro parágrafo com mais conteúdo para testar a extração.</p>
    <a href="https://example.com">Link externo</a>
    <a href="/sobre">Link relativo</a>
    <a href="https://example.com/arquivo.pdf">PDF ignorado</a>
    <a href="#ancora">Âncora ignorada</a>
    <img src="https://example.com/foto.jpg" alt="Foto">
</body>
</html>
"""

parser = Parser()
result = parser.parse(HTML_SAMPLE, "https://meusite.com")

print(f"Título      : {result.title}")
print(f"Descrição   : {result.description}")
print(f"Idioma      : {result.lang}")
print(f"Palavras    : {result.word_count}")
print(f"Links       : {result.links}")
print(f"Imagens     : {result.images}")
print(f"Headings    : {result.headings}")
print(f"Texto       : {result.body_text[:80]}...")
