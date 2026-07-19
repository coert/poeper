FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

RUN mkdir -p /app/data \
    && useradd --create-home --uid 10001 poeper \
    && chown -R poeper:poeper /app

USER poeper

EXPOSE 8000

CMD ["uv", "run", "--frozen", "python", "production.py"]
