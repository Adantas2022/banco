# ===========================================
# BASE IMAGE
# ===========================================
FROM python:3.11-slim as base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install corporate CA certificate (Zscaler)
COPY asa-certificate.cer /usr/local/share/ca-certificates/asa-certificate.crt
RUN update-ca-certificates

# Make pip and requests use the system CA bundle
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    PIP_CERT=/etc/ssl/certs/ca-certificates.crt

RUN find /etc/apt/sources.list.d/ -type f -exec sed -i 's|http://deb.debian.org|https://deb.debian.org|g' {} +

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ===========================================
# BUILDER - Instalar dependências Python
# ===========================================
FROM base as builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar arquivos de dependências
COPY pyproject.toml ./
COPY requirements.lock ./
COPY src/ /app/src/

# Usar requirements.lock para builds reproduzíveis
# Fallback para pyproject.toml se lock não existir
RUN pip install --upgrade pip && \
    if [ -f requirements.lock ]; then \
        pip install -r requirements.lock; \
    else \
        pip install .; \
    fi

# ===========================================
# API SERVICE
# ===========================================
FROM base as api

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY src/ /app/src/
COPY tests/ /app/tests/

# Expor porta
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Comando para rodar a API
CMD ["uvicorn", "irpf_processor.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ===========================================
# WORKER SERVICE (ROUTER)
# ===========================================
FROM base as worker-router

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-por \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ /app/src/
COPY tests/ /app/tests/

CMD ["dramatiq", "irpf_processor.presentation.workers.router_worker", "--processes", "1", "--threads", "2"]

# ===========================================
# WORKER SERVICE (Digital - sem OCR pesado)
# ===========================================
FROM base as worker-digital

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-por \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ /app/src/
COPY tests/ /app/tests/

# RUN pip install --no-cache-dir docling docling-core docling-ibm-models tesserocr

CMD ["dramatiq", "irpf_processor.presentation.workers.extraction_worker", "--processes", "1", "--threads", "1"]

# ===========================================
# WORKER-OCR SERVICE (com Docling + Tesseract)
# ===========================================
FROM base as worker-ocr

ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-por \
    libtesseract-dev \
    libleptonica-dev \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ /app/src/
COPY tests/ /app/tests/

# RUN pip install --no-cache-dir docling docling-core docling-ibm-models tesserocr

CMD ["dramatiq", "irpf_processor.presentation.workers.ocr_worker", "--processes", "1", "--threads", "1"]

# ===========================================
# DEVELOPMENT
# ===========================================
FROM base as dev

# Instalar Tesseract OCR + dependencias de imagem para OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-por \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Copiar dependências instaladas do builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Instalar dependências de desenvolvimento
RUN pip install pytest pytest-asyncio pytest-cov httpx

# Copiar código fonte
COPY . /app/

# Comando padrão
CMD ["bash"]
