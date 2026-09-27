# Docker Setup for RagFlow

This directory contains the Docker setup for the RagFlow application, including all necessary services for development and monitoring.

## Services

| Service | Image | Port | Purpose |
|---|---|---|---|
| **fastapi** | built from `rag/Dockerfile` | `8000` | Main application running on Uvicorn |
| **nginx** | `nginx:stable-alpine3.23` | `80` | Reverse proxy in front of FastAPI |
| **celery-worker** | built from `rag/Dockerfile` | — | Async task processing and vector indexing |
| **flower** | built from `rag/Dockerfile` | `5000` | Celery task monitoring UI |
| **pgvector** | `pgvector/pgvector:0.8.2-pg18-trixie` | `5400` | Vector-enabled PostgreSQL for metadata and PGVector |
| **qdrant** | `qdrant/qdrant:v1.18.0` | `6333`, `6334` | Vector database for similarity search |
| **minio** | `alpine/minio:latest-release` | `9000`, `9001` | S3-compatible object storage for uploaded documents |
| **rabbitmq** | `rabbitmq:4.3.6-management-alpine` | `5672`, `15672` | Celery message broker |
| **redis** | `redis:alpine3.23` | `6379` | Celery result backend |
| **prometheus** | `prom/prometheus:v3` | `9090` | Metrics collection and scraping |
| **grafana** | `grafana/grafana:13.1.0` | `3000` | Visualization dashboards for metrics |
| **postgres-exporter** | `prometheuscommunity/postgres-exporter:v0.19.1` | `9187` | Exports PostgreSQL metrics for Prometheus |
| **node-exporter** | `prom/node-exporter:v1` | `9100` | Host system metrics collection |

All services share the `backend` bridge network and persist data in named volumes
(`fastapi_data`, `pgvector_data`, `qdrant_data`, `minio_data`, `rabbitmq_data`,
`redis_data`, `prometheus_data`, `grafana_data`).

## Setup Instructions

### 1. Set up environment files

Create your environment files from the examples. Every service reads its own `.env`
file from `docker/env/`:

```bash
cd docker/env
cp .env.example.app            .env.app
cp .env.example.postgres       .env.postgres
cp .env.example.grafana        .env.grafana
cp .env.example.postgres-exporter .env.postgres-exporter
cp .env.example.rabbitmq       .env.rabbitmq
cp .env.example.redis          .env.redis
```

`env/.env.app` holds **all** application configuration (LLM keys, Postgres, MinIO,
Celery broker/result URLs) and is baked into the image by the `Dockerfile`.

### 2. Set up the Alembic configuration

```bash
cd docker/rag
cp alembic.example.ini alembic.ini
```

You do not normally need to do this for Docker: `rag/Dockerfile` copies
`docker/rag/alembic.ini` into the image and `rag/entrypoint.sh` runs
`alembic upgrade head` on every container start.

### 3. Start the services

```bash
cd docker
docker compose up --build -d
```

To start only specific services:

```bash
docker compose up -d fastapi nginx pgvector qdrant
```

If you encounter connection issues, you may want to start the infrastructure
services first and let them initialize before starting the application:

```bash
# Start databases and messaging first
docker compose up -d pgvector qdrant minio rabbitmq redis
# Wait for databases to be healthy
sleep 20
# Start the application services
docker compose up -d --build fastapi nginx celery-worker flower prometheus grafana node-exporter postgres-exporter
```

In case deleting all containers and volumes is necessary, you can run:

```bash
docker compose down -v --remove-orphans
```

### 4. Access the services

| Service | URL |
|---|---|
| FastAPI Application (direct) | http://localhost:8000 |
| FastAPI Documentation | http://localhost:8000/docs |
| Nginx (serving FastAPI) | http://localhost |
| Flower (Celery monitor) | http://localhost:5000 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |
| RabbitMQ Management | http://localhost:15672 |
| MinIO Console | http://localhost:9001 |
| Qdrant UI | http://localhost:6333/dashboard |
| PostgreSQL (pgvector) | `localhost:5400` |
| Node Exporter | http://localhost:9100 |
| PostgreSQL Exporter | http://localhost:9187 |

Default credentials: Grafana `admin` / the value of `GF_SECURITY_ADMIN_PASSWORD` in
`env/.env.grafana`; RabbitMQ `RABBITMQ_DEFAULT_USER` / `RABBITMQ_DEFAULT_PASS` in
`env/.env.rabbitmq`; MinIO `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` in `env/.env.app`.

## Celery Task Queues

The worker consumes four queues, routed in `src/celery_app.py`:

| Queue | Task | Module |
|---|---|---|
| `file_processing` | `process_project_file` | `src/tasks/file_processing.py` |
| `data_indexing` | `index_data_content` | `src/tasks/data_indexing.py` |
| `process` | `process_workflow` (chains the two above) | `src/tasks/process_workflow.py` |
| `default` | any task without an explicit route | — |

Tune the worker with:

- `CELERY_WORKER_CONCURRENCY` — number of worker processes (default `2`)
- `CELERY_TASK_TIME_LIMIT` — hard per-task timeout in seconds (default `600`)
- `CELERY_TASK_ACKS_LATE` — ack after execution for at-least-once delivery
- `CELERY_RESULT_BACKEND` — Redis URL; results are retained for 1 hour

## Volume Management

### Managing Docker Volumes

Docker volumes are used to persist data generated by and used by Docker containers. Here are some commands to manage your volumes:

1. **List all volumes**:
   ```bash
   docker volume ls
   ```
2. **Inspect a volume**:
   ```bash
   docker volume inspect <volume_name>
   ```

   - list files in a volume:
   ```bash
   docker run --rm -v <volume_name>:/data busybox ls -l /data
   ```

3. **Remove a volume**:
   ```bash
   docker volume rm <volume_name>
   ```
4. **Prune unused volumes**:
    ```bash
    docker volume prune
    ```
5. **Backup volume for migration**:
    ```bash
    docker run --rm -v <volume_name>:/volume -v $(pwd):/backup alpine tar cvf /backup/backup.tar /volume
    ```
6. **Restore volume from backup**:
    ```bash
    docker run --rm -v <volume_name>:/volume -v $(pwd):/backup alpine sh -c "cd /volume && tar xvf /backup/backup.tar --strip 1"
    ```
7. **Remove all volumes**:
    ```bash
    docker volume rm $(docker volume ls -q)
    ```

**NOTE**: For PostgreSQL specifically, you might want to consider using PostgreSQL's built-in tools like `pg_dump` and `pg_restore` for more reliable backups, especially for live databases.

## Monitoring

### FastAPI Metrics

FastAPI is configured to expose Prometheus metrics at the
`/59f5e3d2-8d9d-4b74-a1d1-6d6a5b4c2f8e` endpoint (hidden from the OpenAPI schema).
These metrics include:

- `http_request_total` — request counts by method, endpoint and status
- `http_request_duration_seconds` — request latency histograms

`prometheus/prometheus.yml` scrapes that same path for the `fastapi` job, so
Prometheus picks the metrics up automatically.

### Scraped targets

| Job | Target | Path |
|---|---|---|
| `fastapi` | `fastapi:8000` | `/59f5e3d2-8d9d-4b74-a1d1-6d6a5b4c2f8e` |
| `node-exporter` | `node-exporter:9100` | `/metrics` |
| `qdrant` | `qdrant:6333` | `/metrics` |
| `postgres` | `postgres-exporter:9187` | `/metrics` |

### Visualizing Metrics in Grafana

1. Log into Grafana at http://localhost:3000 (default credentials: admin/admin_password)
2. Add Prometheus as a data source (URL: http://prometheus:9090)
3. Import dashboards for FastAPI, PostgreSQL, and Qdrant

#### Dashboards URLs

https://grafana.com/grafana/dashboards/18739-fastapi-observability/

https://grafana.com/grafana/dashboards/1860-node-exporter-full/

https://grafana.com/grafana/dashboards/23033-qdrant/

https://grafana.com/grafana/dashboards/12485-postgresql-exporter/

### Task Monitoring with Flower

Background ingestion and indexing is asynchronous, so watch it in Flower at
http://localhost:5000. It shows per-task state, progress and results for the
`file_processing`, `data_indexing` and `process` queues.

## Development Workflow

The FastAPI application is configured with hot-reloading. Any changes to the code in the `src/` directory will automatically reload the application.
