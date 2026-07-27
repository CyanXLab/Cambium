FROM python:3.12-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml README.md ./
COPY app/ ./app/
COPY plugins/ ./plugins/
COPY docs/ ./docs/

# Install Python dependencies (base only — use [all] for full features)
RUN pip install --no-cache-dir -e ".[vector]"

# Create data directories
RUN mkdir -p /app/app/data/uploads /app/workspace /app/custom_tools /app/.skills

# Expose port
EXPOSE 3000

# Environment defaults (override at runtime)
ENV CAMBIUM_LOG_LEVEL=INFO \
    CAMBIUM_LOG_FORMAT=json \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000/api/health || exit 1

# Run
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3000", "--log-level", "info"]
