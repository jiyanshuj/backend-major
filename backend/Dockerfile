# Use Python 3.10 slim as base image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies for dlib, face_recognition, and OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk2.0-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    pkg-config \
    wget \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file first (for better Docker layer caching)
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy all application files
COPY . .

# Create directories for models and temp files
RUN mkdir -p /app/models /app/temp

# Expose port (Render uses PORT environment variable)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1

# Start application with dynamic port from Render
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1