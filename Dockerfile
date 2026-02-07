FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/root/.local/bin:$PATH"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv (dependency manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

COPY pyproject.toml /app/pyproject.toml

# Install runtime dependencies (no dev)
RUN uv sync --no-dev

COPY . /app

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

