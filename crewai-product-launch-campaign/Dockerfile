FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Environment variables
ENV REGOLO_API_KEY=""
ENV PORT=5000

EXPOSE 5000

CMD ["python", "api_server.py"]
