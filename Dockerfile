# ===========================================
# BASE
# ===========================================

FROM asascfi.jfrog.io/docker-virtual-asa/python:3.11-slim AS base
#FROM python:3.11-slim as base

WORKDIR /app

# 1. Declarar as credenciais na base para podermos autenticar o apt-get
ARG JFROG_USER
ARG JFROG_TOKEN

# 2. Configurar a autenticação do APT de forma segura (não fica salvo no sources.list)
RUN echo "machine asascfi.jfrog.io login ${JFROG_USER} password ${JFROG_TOKEN}" > /etc/apt/auth.conf.d/jfrog.conf

# 3. Substituir os endereços oficiais do Debian pela URL do seu JFrog
# ATENÇÃO: Substitua a palavra "debian-virtual" pelo nome correto do seu repositório Debian/Ubuntu lá no JFrog!
RUN sed -i 's|http://deb.debian.org|https://asascfi.jfrog.io/artifactory/asa-debian-virtual|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true && \
    sed -i 's|http://security.debian.org|https://asascfi.jfrog.io/artifactory/asa-debian-virtual|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true && \
    sed -i 's|http://deb.debian.org|https://asascfi.jfrog.io/artifactory/asa-debian-virtual|g' /etc/apt/sources.list 2>/dev/null || true && \
    sed -i 's|http://security.debian.org|https://asascfi.jfrog.io/artifactory/asa-debian-virtual|g' /etc/apt/sources.list 2>/dev/null || true

# 4. Agora o apt-get update vai bater no seu JFrog com sucesso!
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*


# ===========================================
# BUILDER - Instalar dependências Python
# ===========================================
FROM base as builder

ARG JFROG_USER
ARG JFROG_TOKEN

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar arquivos de dependências
COPY pyproject.toml ./
COPY requirements.lock ./
COPY src/ /app/src/

# Usar requirements.lock para builds reproduzíveis
# Fallback para pyproject.toml se lock não existir
# NOTA: O pip aqui já vai usar o JFrog automaticamente devido ao ENV na base
RUN PIP_INDEX_URL="https://${JFROG_USER}:${JFROG_TOKEN}@asascfi.jfrog.io/artifactory/api/pypi/pypi-virtual/simple" \
    pip install --upgrade pip && \
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
# WORKER SERVICE (Digital - sem OCR pesado)
# ===========================================
FROM base as worker

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

CMD ["dramatiq", "irpf_processor.presentation.workers", "--processes", "2", "--threads", "4"]

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

# O pip aqui também utilizará o JFrog automaticamente
RUN pip install --no-cache-dir docling docling-core docling-ibm-models tesserocr

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
# O pip aqui também utilizará o JFrog automaticamente
RUN pip install pytest pytest-asyncio pytest-cov httpx

# Copiar código fonte
COPY . /app/

# Comando padrão
CMD ["bash"]