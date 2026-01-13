FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY *.py ./
COPY data/ ./data/

# Create directories
RUN mkdir -p rag_index

# Expose port
EXPOSE 8000

# Run application
CMD ["python", "main.py"]
