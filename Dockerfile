FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and OCR stack
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-deu \
    tesseract-ocr-nor \
    ghostscript \
    poppler-utils \
    libtiff5 \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency metadata and install
COPY pyproject.toml poetry.lock* README.md ./
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --only main --no-interaction --no-ansi --no-root

# Copy the rest of the application
COPY . .

# Create state directories and ensure script is executable
RUN mkdir -p /app/state /state && \
    chmod +x ./scripts/start_ingestion.sh

# Non-root user
RUN useradd -m -u 1000 mnemosyne && \
    chown -R mnemosyne:mnemosyne /app /state
USER mnemosyne

# Ensure Python can find the package in src/
ENV PYTHONPATH=/app/src

# Default command runs the startup script that ingests everything and keeps the vault watcher alive
CMD ["./scripts/start_ingestion.sh"]
