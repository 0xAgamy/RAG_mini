<div align="center">

# RAGmini

**A production-grade Retrieval-Augmented Generation (RAG) platform**  
built with clean architecture, multi-provider LLM support, dual vector stores, and a full observability stack.

[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white)](https://docker.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-PGVector-336791?style=flat&logo=postgresql&logoColor=white)](https://postgresql.org)
[![MongoDB](https://img.shields.io/badge/MongoDB-Motor-47A248?style=flat&logo=mongodb&logoColor=white)](https://mongodb.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[Features](#-features) · [Architecture](#-architecture) · [Quick Start](#requirements) · [Monitoring](#monitoring)

</div>

##  Overview

miniRAG is a fully containerised, production-ready RAG system that lets you ingest documents, embed them into a vector store, and query them using natural language — powered by your choice of LLM provider and vector database.

Built with **MVC architecture**, **Factory Design Patterns**, and a complete **Prometheus + Grafana observability stack**, this is not a notebook demo — it is a deployable backend service.

---

## ✨ Features

- **Multi-provider LLM support** — swap between OpenAI, Cohere, and Ollama (local) at runtime with zero code changes
- **Dual vector store support** — Qdrant and PGVector (PostgreSQL), switchable via configuration
- **HNSW indexing** — optimised vector search with batch embedding and indexing
- **MVC architecture** — clean separation of Controllers, Services, Schemas, and Models
- **Factory Design Pattern** — for both LLM providers and Vector DB backends
- **Multilingual template parser** — dynamic prompt templates supporting multiple languages
- **Async throughout** — FastAPI + async SQLAlchemy + Motor (async MongoDB driver)
- **Database migrations** — Alembic-managed schema versioning for PostgreSQL
- **Full observability** — Prometheus metrics, Grafana dashboards, Nginx reverse proxy, Postgres Exporter, Node Exporter
- **Security-first** — file content validation (not just extension), no internal exposure of sensitive configs
- **Chunked file uploads** — with aiofiles for non-blocking I/O
- **Dynamic asset management** — assets collection with MongoDB indexing (in v1) and PostgreSQL JSONB storage

---


## 🏗 Architecture

```
                         ┌─────────────────────────────────────┐
                         │           Nginx Reverse Proxy       │
                         └──────────────┬──────────────────────┘
                                        │
                         ┌──────────────▼─────────────────────┐
                         │         FastAPI Application        │
                         │   (MVC · Pydantic · Depends · DI)  │
                         └──┬────────────┬──────────┬─────────┘
                            │            │          │
               ┌────────────▼──┐  ┌──────▼──────┐  ┌▼────────────────┐
               │  Controllers  │  │   Schemas   │  │    Middleware   │
               │  (Business    │  │  (Pydantic  │  │ (Metrics · Log) │
               │   Logic)      │  │   Models)   │  └─────────────────┘
               └──────┬────────┘  └─────────────┘
                      │
                      ┼────────────┐
                      │            │
                 ┌────▼──────┐ ┌───▼──────────────────┐
                 │PostgreSQL │ │   LLM Factory        │
                 │(SQLAlchemy│ │ ┌──────────────────┐ │
                 │+ Alembic) │ │ │ OpenAI  │ Cohere │ │
                 │           │ │ │ Ollama (local)   │ │
                 │ Projects  │ │ └──────────────────┘ │
                 │ Assets    │ └───▼──────────────────┘
                 │ Chunks    │     │
                 └───────────┘     │
                                   │
                    ┌──────────────▼──────────────┐
                    │       VectorDB Factory      │
                    │  ┌──────────┬─────────────┐ │
                    │  │  Qdrant  │   PGVector  │ │
                    │  │          │(HNSW Index) │ │
                    │  └──────────┴─────────────┘ │
                    └─────────────────────────────┘

                    ┌─────────────────────────────┐
                    │      Observability Stack    │
                    │  Prometheus · Grafana       │
                    │  Postgres Exporter          │
                    │  Node Exporter              │
                    └─────────────────────────────┘
```

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| **API Framework** | FastAPI, Pydantic v2, Pydantic-Settings |
| **Async I/O** | aiofiles, asyncio, async SQLAlchemy |
| **LLM Providers** | OpenAI, Cohere, Ollama (local) |
| **Vector Stores** | Qdrant, PGVector (PostgreSQL extension) |
| **Relational DB** | PostgreSQL + SQLAlchemy + Alembic |
| **Vector Indexing** | HNSW (Hierarchical Navigable Small World) |
| **Reverse Proxy** | Nginx |
| **Observability** | Prometheus, Grafana, Postgres Exporter, Node Exporter |
| **Containerisation** | Docker, Docker Compose |
| **Design Patterns** | Factory, MVC, Dependency Injection, ABC Interface |

---

## Requirements

 - python 3.14
  
### Installation 

### Install The Required packages

```bash
pip install -r requirements.txt
```

### Setup the environment variables

```bash
cp .env.example .env
```
### Run Docker Compose Services

```bash

 cd docker
 cp .env.exmaple .env 
```

```bash

cd docker
sudo docker compose up -d 
```

###  Access the services

| Service | URL |
|---|---|
| API Docs (Swagger) | http://localhost/docs |
| Grafana Dashboard | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Qdrant UI | http://localhost:6333/dashboard |

---

##  Monitoring

RAGmini ships with a complete observability stack out of the box.

**Grafana Dashboards include:**
- Request rate, latency (p50, p95, p99) per endpoint
- Embedding throughput and vector search latency
- PostgreSQL query performance and connection pool stats
- System metrics (CPU, memory, disk) via Node Exporter

**Prometheus scrapes:**
- FastAPI `/metrics` endpoint (custom middleware)
- Postgres Exporter
- Node Exporter

To access Grafana: `http://localhost:3000` 
Import the bundled dashboard JSON from `/grafana/dashboards/`.

---

## Security Notes

- File content is validated beyond extension — MIME type and byte-level inspection
- No internal configuration or secrets are exposed through API responses
- All database connections use environment-injected credentials
- Nginx handles TLS termination and rate limiting in production

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---


<div align="center">
Built with ❤️ by <a href="https://github.com/0xAgamy">Mohamed Elagamy</a>
</div>

