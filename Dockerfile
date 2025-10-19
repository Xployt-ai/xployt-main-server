FROM python:3.13-slim

# Ensure Python runs in an unbuffered mode and avoids writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (keep minimal)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for better build caching
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

# Copy the rest of the application
COPY . /app

# Create non-root user and ensure storage path is writable
RUN useradd -ms /bin/bash appuser \
    && mkdir -p /app/local_storage/repos \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Run the FastAPI app with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


