# Use official uv image with Python 3.12
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml ./

# Install dependencies defined in pyproject.toml
RUN uv sync --no-cache

# Copy application code (excluding common/lib)
COPY main.py .
COPY a2a_client_utils.py .
COPY state_manager.py .

EXPOSE 8501

CMD ["uv", "run", "streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]