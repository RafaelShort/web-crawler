<div align="center">

# 🕷️ Web Crawler

**Motor de crawling distribuído com busca full-text e painel de monitoramento em tempo real**

[![Python](https://img.shields.io/badge/Python-3.12-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![MongoDB](https://img.shields.io/badge/MongoDB-7-47a248?style=flat-square&logo=mongodb&logoColor=white)](https://mongodb.com)
[![Elasticsearch](https://img.shields.io/badge/Elasticsearch-8.13-005571?style=flat-square&logo=elasticsearch&logoColor=white)](https://elastic.co)
[![RabbitMQ](https://img.shields.io/badge/RabbitMQ-3.13-ff6600?style=flat-square&logo=rabbitmq&logoColor=white)](https://rabbitmq.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ed?style=flat-square&logo=docker&logoColor=white)](https://docker.com)

![Dashboard](https://img.shields.io/badge/UI-Dashboard%20%7C%20Crawler%20%7C%20Busca%20%7C%20Serviços-1e293b?style=flat-square)

</div>

---

## 📋 Visão Geral

Projeto de portfólio que implementa um **web crawler assíncrono** com painel de monitoramento em tempo real.

O sistema é composto por um motor de crawling assíncrono, uma API REST e uma interface web com atualização automática, todos orquestrados via Docker Compose.

---

## ✨ Funcionalidades

### 🕷️ Crawler
- Crawling assíncrono com workers paralelos configuráveis
- Controle de profundidade máxima de navegação
- **Bloom Filter** para deduplicação eficiente de URLs sem repetição de visitas
- Respeito a políticas de crawling (rate limiting por domínio)
- Extração de título, descrição, texto, links, imagens e headings
- Fallback progressivo de descrição (meta → og → twitter → primeiro parágrafo → body)

### 🔍 Busca
- Busca full-text com Elasticsearch com scoring por relevância
- Campos ponderados: título (×3), descrição (×2), corpo da página (×1)
- Filtros por domínio e idioma
- Paginação completa com ellipsis

### 📊 Monitoramento
- Dashboard com métricas em tempo real (atualização a cada 10 s)
- Healthcheck de todos os serviços dependentes
- Estatísticas de MongoDB, RabbitMQ e Fetcher
- Controle do crawler via interface web (iniciar / parar)

### 🔌 API REST
- Documentação automática via Swagger UI (`/docs`) e ReDoc (`/redoc`)
- Endpoints para controle do crawler, busca e health check

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| **API & Backend** | FastAPI, Uvicorn, Pydantic |
| **Crawler** | aiohttp, BeautifulSoup4, lxml |
| **Fila de mensagens** | RabbitMQ (aio-pika) |
| **Banco de dados** | MongoDB (pymongo) |
| **Busca full-text** | Elasticsearch 8 |
| **Frontend** | Jinja2, Alpine.js, Tailwind CSS |
| **Infraestrutura** | Docker, Docker Compose |
| **Observabilidade** | Loguru |

---

## Como Executar

### Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) e [Docker Compose](https://docs.docker.com/compose/)

### 1. Clonar o repositório

```bash
git clone https://github.com/seu-usuario/web-crawler.git
cd web-crawler
```

### 2. Configurar variáveis de ambiente

```bash
cp .env.example .env
```
### 3. Subir os serviços

```bash
docker compose up -d --build
```

### 4. Aguardar os healthchecks

```bash
docker compose ps
```

### 5. Acessar

- Interface Web:	http://localhost:8080
- Swagger UI:	http://localhost:8080/docs
- ReDoc:	http://localhost:8080/redoc
- RabbitMQ Management:	http://localhost:15672 (guest/guest)
- Elasticsearch:	http://localhost:9200

## 📖 API Reference

### Crawler

```http
POST /api/v1/crawler/start
Content-Type: application/json

{
  "seed_urls": ["https://example.com"],
  "max_depth": 2,
  "max_workers": 5
}
```

```http
POST /api/v1/crawler/stop
```

```http
GET /api/v1/crawler/status
```

### Busca

```http
GET /api/v1/search?q=python&domain=docs.python.org&lang=en&size=10&page=1
```

Resposta:

```json
{
  "query": "python",
  "total": 42,
  "page": 1,
  "size": 10,
  "total_pages": 5,
  "results": [
    {
      "url": "https://docs.python.org/3/",
      "title": "Python 3 Documentation",
      "description": "Welcome to Python 3!",
      "domain": "docs.python.org",
      "lang": "en",
      "score": 8.34,
      "crawled_at": "2026-05-10T20:37:10.632128"
    }
  ]
}
```
### Health

```http
GET /api/v1/health
```

Resposta:

```json
{
  "status": "ok",
  "services": {
    "mongodb":       { "status": "ok", "uri": "mongodb://mongo:27017" },
    "elasticsearch": { "status": "ok", "version": "8.13.0" },
    "rabbitmq":      { "status": "ok", "uri": "amqp://..." }
  }
}
```

## Detalhes Técnicos

### Bloom Filter
Estrutura de dados probabilística usada para checar se uma URL já foi visitada sem armazenar todas as URLs em memória. Aceita uma taxa de falso-positivo configurável, eliminando revisitas com custo de memória O(1).

### Busca Ponderada
O Elasticsearch usa multi_match com pesos diferenciados por campo:

- Título → peso 3× (mais relevante para a busca)
- Descrição → peso 2×
- Corpo da página → peso 1×

### Fallback de Descrição
O parser tenta extrair a descrição em 6 níveis progressivos antes de retornar vazio, garantindo que a maioria das páginas tenha uma descrição útil mesmo sem `<meta description>`.