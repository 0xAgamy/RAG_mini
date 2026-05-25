FROM ghcr.io/astral-sh/uv:0.11.15-python3.13-alpine

WORKDIR /app


RUN apk add --no-cache \
    build-base \
    libavif-dev \
    pkgconfig \
    libjpeg-turbo-dev \
    gcc \
    zip \
    unzip \
    python3-dev \
    libxml2-dev \
    libxslt-dev \
    curl

COPY src/requirements.txt .
RUN uv pip install -r requirements.txt --system

COPY src/ .

RUN mkdir -p /models/db_schemes/ragdb/

COPY docker/rag/alembic.ini /app/models/db_schemes/ragdb/alembic.ini
COPY docker/env/.env.app .env
COPY docker/rag/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

ENTRYPOINT [ "/entrypoint.sh" ]

CMD [ "uvicorn", "main:app","--host", "0.0.0.0" , "--port", "8000", "--workers", "4" ]
