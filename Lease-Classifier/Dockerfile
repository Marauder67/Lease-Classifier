FROM python:3.11-slim

# Keep Python output unbuffered and skip .pyc files in the container
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first (better build caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY app/ ./app/
COPY examples/ ./examples/

EXPOSE 8000

# Serve the API. In production put this behind a reverse proxy / load balancer.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
