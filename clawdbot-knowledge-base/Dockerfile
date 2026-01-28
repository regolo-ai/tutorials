FROM python:3.11-slim

LABEL maintainer="Regolo AI <support@regolo.ai>"
LABEL description="Clawdbot Knowledge Base with Regolo GPU"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY rag_pipeline.py telegram_handler.py kb_bot.py test_retrieval.py ./

# Create necessary directories
RUN mkdir -p /app/knowledge-base /app/index /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python3 -c "import sys; sys.exit(0)"

# Run bot
CMD ["python3", "kb_bot.py"]
