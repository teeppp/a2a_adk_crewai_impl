# Use official uv image with Python 3.12
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml ./

# Install dependencies defined in pyproject.toml
RUN uv sync --no-cache

# Copy application code (excluding common)
COPY main.py .
COPY crewai_config.yaml .

EXPOSE 8002

CMD ["uv", "run", "python", "main.py"]