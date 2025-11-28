# Use Ubuntu base with Python (better package support)
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 python3.10-dev python3-pip \
    build-essential cmake git wget pkg-config \
    libopenblas-dev liblapack-dev libboost-all-dev \
    libx11-dev libgtk-3-dev libgl1 libglib2.0-0 \
    libsm6 libxext6 libxrender1 libgomp1 \
    libjpeg-dev libpng-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.10 /usr/bin/python && \
    ln -sf /usr/bin/python3.10 /usr/bin/python3

RUN python3 -m pip install --upgrade pip setuptools wheel

WORKDIR /app

COPY requirements.txt .

# Install numpy first
RUN pip install --no-cache-dir numpy==1.24.3

# Install precompiled dlib (instant, no memory issues)
RUN pip install --no-cache-dir dlib-bin

# Install everything else
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/models /app/temp

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
