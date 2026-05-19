# 🏛️ IRPF Processor

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green?logo=fastapi&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-7.0-green?logo=mongodb&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7.0-red?logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-1.5+-purple?logo=terraform&logoColor=white)
![Azure](https://img.shields.io/badge/Azure-Cloud-0078D4?logo=microsoftazure&logoColor=white)
![GCP](https://img.shields.io/badge/GCP-Cloud-4285F4?logo=googlecloud&logoColor=white)
![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-Tracing-purple?logo=opentelemetry&logoColor=white)
![Tesseract](https://img.shields.io/badge/Tesseract-OCR-orange?logo=google&logoColor=white)
![License](https://img.shields.io/badge/License-Proprietary-orange)

**Plataforma de extração inteligente de dados de Declarações IRPF**

[Quick Start](#-quick-start) •
[API](#-api-endpoints) •
[Segurança](#-segurança) •
[OCR](#-ocr-processing) •
[DevSecOps](#-devsecops--infrastructure-as-code) •
[Observabilidade](#-observabilidade)

</div>

---

## 📋 Índice

- [Sobre o Projeto](#-sobre-o-projeto)
- [Quick Start](#-quick-start)
- [Pré-requisitos](#-pré-requisitos)
- [Instalação](#-instalação)
- [Configuração](#-configuração)
- [Segurança](#-segurança)
- [API Endpoints](#-api-endpoints)
- [OCR Processing](#-ocr-processing)
- [Testes](#-testes)
- [Arquitetura](#-arquitetura)
- [DevSecOps & Infrastructure as Code](#-devsecops--infrastructure-as-code)
- [Observabilidade](#-observabilidade)
- [Troubleshooting](#-troubleshooting)
- [Contribuindo](#-contribuindo)

---

## 🎯 Sobre o Projeto

O **IRPF Processor** é uma plataforma backend enterprise para:

- 📤 **Upload** de Declarações de Imposto de Renda (PDF)
- 🔍 **Extração** automática de dados com 10 extratores especializados
- 🔎 **OCR** para documentos escaneados (Tesseract + Docling)
- 📊 **Detecção** automática de versão (2023, 2024, 2025)
- 🔎 **Busca** por CPF, nome, ano, cidade, estado
- 🔒 **Segurança** com autenticação API Key e multi-tenancy
- 📈 **Observabilidade** completa com métricas, logs e tracing distribuído

### Principais Features

| Feature | Descrição |
|---------|-----------|
| **Parser Inteligente** | 10 extratores de seção com Strategy Pattern |
| **OCR Dual-Engine** | Tesseract (primário) + Docling IBM (fallback) |
| **Detecção PDF** | Classifica DIGITAL, IMAGE ou MIXED automaticamente |
| **Multi-versão** | Templates YAML para cada ano-exercício |
| **Alta Performance** | ~0.5s (digital) / ~30s (OCR) por documento |
| **Segurança M2M** | API Key authentication com scopes |
| **Observabilidade** | Prometheus + Grafana + Jaeger + Structured Logging |
| **Multi-tenant** | Isolamento completo por tenant |

### Resultados de Performance

| Tipo PDF | Engine | Tempo | Confiança |
|----------|--------|-------|-----------|
| DIGITAL | pdfplumber | ~0.5s | **95%** |
| IMAGE (scan) | Tesseract | ~30s | **70%** |
| IMAGE (fallback) | Docling | ~200s | **72%** |

---

## 🚀 Quick Start

```bash
# 1. Clonar o repositório
git clone https://github.com/AsaBank/asa-nfe-process.git
cd asa-nfe-process

# 2. Copiar variáveis de ambiente
cp env.example .env

# 3. Subir toda a infraestrutura
docker compose up -d

# 4. Verificar se está rodando
curl http://localhost:8000/health

# 5. Criar API Key de administrador
python -m irpf_processor.cli.create_api_key \
  --tenant-id meu-tenant \
  --name "Admin Key" \
  --admin

# 6. Testar upload de documento (use a API Key gerada)
curl -X POST http://localhost:8000/v1/documents \
  -H "X-Tenant-ID: meu-tenant" \
  -H "Authorization: Bearer irpf_ak_xxxxx" \
  -F "file=@docs/IRPF/Geral-IRPF-2025-2024.pdf"
```

**Pronto!** 🎉 A aplicação está rodando em http://localhost:8000

---

## 📦 Pré-requisitos

### Obrigatórios

| Ferramenta | Versão Mínima | Verificar |
|------------|---------------|-----------|
| Docker | 24.0+ | `docker --version` |
| Docker Compose | 2.20+ | `docker compose version` |
| Git | 2.40+ | `git --version` |

### Para Desenvolvimento Local (Opcional)

| Ferramenta | Versão | Verificar |
|------------|--------|-----------|
| Python | 3.11+ | `python --version` |
| Tesseract | 5.0+ | `tesseract --version` |
| pip | Última | `pip --version` |

---

## 🔧 Instalação

### Opção 1: Docker (Recomendado)

```bash
# Subir todos os serviços
docker compose up -d

# Verificar status
docker compose ps

# Ver logs
docker compose logs -f api worker-router worker-digital worker-ocr
```

### Opção 2: Desenvolvimento Local

```bash
# Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac

# Instalar dependências (versões travadas)
pip install -r requirements.lock

# Ou instalar em modo desenvolvimento
pip install -e ".[dev]"

# Instalar Tesseract (macOS)
brew install tesseract tesseract-lang

# Instalar Tesseract (Ubuntu)
sudo apt-get install tesseract-ocr tesseract-ocr-por

# Subir apenas infraestrutura
docker compose up -d mongo redis minio jaeger prometheus pushgateway grafana

# Rodar API localmente
uvicorn irpf_processor.main:app --reload --port 8000

# Em outro terminal, rodar Workers
dramatiq irpf_processor.presentation.workers --queues extraction-router
dramatiq irpf_processor.presentation.workers --queues default
dramatiq irpf_processor.presentation.workers.ocr_worker --queues extraction-ocr
```

---

## ⚙️ Configuração

### Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
# Ambiente
APP_ENV=development
LOG_LEVEL=INFO

# MongoDB
MONGO_URI=mongodb://mongo:27017
MONGO_DB=irpf_processor

# Redis
REDIS_URL=redis://redis:6379/0

# MinIO (S3-compatible)
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=documents
MINIO_SECURE=false

# OCR
OCR_TIMEOUT_SECONDS=300

# OpenTelemetry (Tracing)
OTEL_ENABLED=true
OTEL_SERVICE_NAME=irpf-processor
OTEL_EXPORTER_ENDPOINT=http://jaeger:4317
OTEL_SAMPLE_RATE=1.0
```

### Portas Utilizadas

| Serviço | Porta | Descrição |
|---------|-------|-----------|
| API | 8000 | FastAPI REST API |
| MongoDB | 27017 | Document Store |
| Redis | 6379 | Broker + Streams |
| MinIO API | 9000 | Object Storage |
| MinIO Console | 9001 | Web UI |
| Prometheus | 9095 | Métricas |
| Pushgateway | 9091 | Worker Metrics |
| Grafana | 3000 | Dashboards |
| **Jaeger** | 16686 | Distributed Tracing UI |

---

## 🔒 Segurança

### Autenticação API Key (M2M)

Todos os endpoints de negócio requerem autenticação via API Key no header `Authorization`:

```bash
curl -H "Authorization: Bearer irpf_ak_xxxxx" \
     -H "X-Tenant-ID: meu-tenant" \
     http://localhost:8000/v1/documents
```

### Criar Primeira API Key (Bootstrap)

```bash
python -m irpf_processor.cli.create_api_key \
  --tenant-id meu-tenant \
  --name "Admin Key" \
  --admin
```

> ⚠️ **Importante:** Guarde a API Key gerada! Ela não será exibida novamente.

### Gerenciar API Keys via API

```bash
# Criar nova chave
curl -X POST http://localhost:8000/v1/auth/keys \
  -H "Authorization: Bearer $ADMIN_API_KEY" \
  -H "X-Tenant-ID: meu-tenant" \
  -H "Content-Type: application/json" \
  -d '{"name": "Chave Leitura", "scopes": ["documents:read", "search:read"]}'

# Listar chaves
curl http://localhost:8000/v1/auth/keys \
  -H "Authorization: Bearer $ADMIN_API_KEY" \
  -H "X-Tenant-ID: meu-tenant"

# Revogar chave
curl -X POST http://localhost:8000/v1/auth/keys/{key_id}/revoke \
  -H "Authorization: Bearer $ADMIN_API_KEY" \
  -H "X-Tenant-ID: meu-tenant"
```

### Scopes Disponíveis

| Scope | Permissão |
|-------|-----------|
| `documents:write` | Upload de documentos |
| `documents:read` | Consultar status e resultado |
| `search:read` | Buscar declarações |
| `admin:keys` | Gerenciar API Keys |

### Multi-tenancy

Todos os dados são isolados por `tenant_id`. A API Key está vinculada a um tenant e só pode acessar dados desse tenant.

### Deduplicação

O sistema usa SHA256 para evitar reprocessamento de PDFs duplicados.

---

## 🔌 API Endpoints

### Health & Metrics (Públicos)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/health` | Liveness check |
| GET | `/ready` | Readiness check |
| GET | `/metrics` | Métricas Prometheus |

### Authentication

| Método | Endpoint | Descrição | Scope |
|--------|----------|-----------|-------|
| POST | `/v1/auth/keys` | Criar API Key | `admin:keys` |
| GET | `/v1/auth/keys` | Listar API Keys | `admin:keys` |
| POST | `/v1/auth/keys/{id}/revoke` | Revogar API Key | `admin:keys` |

### Documents

| Método | Endpoint | Descrição | Scope |
|--------|----------|-----------|-------|
| POST | `/v1/documents` | Upload de PDF | `documents:write` |
| GET | `/v1/documents/{id}` | Obter resultado | `documents:read` |
| GET | `/v1/documents/{id}/status` | Obter status | `documents:read` |

### Search

| Método | Endpoint | Descrição | Scope |
|--------|----------|-----------|-------|
| GET | `/v1/irpf/search` | Busca com filtros | `search:read` |
| GET | `/v1/irpf/search/by-cpf/{cpf}` | Busca por CPF | `search:read` |
| GET | `/v1/irpf/search/stats` | Estatísticas | `search:read` |

### Documentação Interativa

- **Swagger UI:** http://localhost:8000/docs (apenas em desenvolvimento)
- **ReDoc:** http://localhost:8000/redoc (apenas em desenvolvimento)

---

## 🔍 OCR Processing

### Arquitetura OCR

O sistema detecta automaticamente o tipo de PDF e roteia para o pipeline adequado:

```
PDF Upload
    │
    ▼
┌───────────────┐
│ Router Worker │ ─── Detecta tipo do PDF
└───────┬───────┘
        │
        ├─── DIGITAL ──▶ worker-digital ──▶ pdfplumber (~0.5s)
        │
        └─── IMAGE/MIXED ──▶ worker-ocr
                                │
                                ├─ 1º Tesseract (primário) ~30s
                                │
                                └─ 2º Docling (fallback) ~200s
                                   (só se Tesseract < 50%)
```

### Tipos de PDF

| Tipo | Descrição | Engine |
|------|-----------|--------|
| **DIGITAL** | PDF com texto nativo | pdfplumber |
| **IMAGE** | PDF escaneado (imagem) | Tesseract/Docling |
| **MIXED** | PDF com páginas digitais e escaneadas | Tesseract/Docling |

### OCR Engines

#### Tesseract (Primário)
- OCR open-source mantido pelo Google
- Rápido (~30s por documento)
- Bom para documentos limpos
- Confiança típica: 70%

#### Docling (Fallback)
- IBM Document Understanding
- Modelos de Deep Learning (PyTorch)
- Excelente para tabelas complexas
- Mais lento (~200s) mas mais preciso
- Usado quando Tesseract < 50% confiança

### Workers OCR

| Worker | Fila | Função |
|--------|------|--------|
| `worker-router` | `extraction-router` | Detecta tipo e roteia |
| `worker-digital` | `default` | Processa PDFs digitais |
| `worker-ocr` | `extraction-ocr` | Processa PDFs escaneados |

---

## 📊 Calculo de Confianca

O sistema utiliza um **servico centralizado de calculo de confianca** baseado no **Strategy Pattern**, permitindo algoritmos especificos para cada tipo de documento.

### Arquitetura do Servico

```
src/irpf_processor/domain/services/confidence/
├── interface.py              # IConfidenceCalculator + ConfidenceResult
├── declaration_calculator.py # Calculo para declaracoes IRPF
├── receipt_calculator.py     # Calculo para recibos
├── ocr_calculator.py         # Decorator para penalidades OCR
└── factory.py                # Factory para selecao dinamica
```

### Niveis de Confianca

| Nivel | Faixa | Descricao |
|-------|-------|-----------|
| **Excelente** | 85% - 100% | Todos os campos obrigatorios + maioria opcionais |
| **Boa** | 70% - 84% | Campos obrigatorios + alguns opcionais |
| **Media** | 50% - 69% | Campos obrigatorios parciais |
| **Baixa** | 0% - 49% | Documento com problemas de extracao |

### Campos Ponderados (Declaracao IRPF)

| Campo | Peso | Obrigatorio |
|-------|------|-------------|
| `taxpayer_identification.normalized_cpf` | 1.0 | Sim |
| `taxpayer_identification.name` | 1.0 | Sim |
| `taxpayer_identification.exercise_year` | 0.8 | Nao |
| `taxpayer_identification.calendar_year` | 0.8 | Nao |
| `assets_declaration` | 0.9 | Nao |
| `income_from_legal_person_to_holder` | 0.9 | Nao |
| `exempt_income` | 0.7 | Nao |
| `exclusive_taxation_income` | 0.7 | Nao |
| `debts_and_encumbrances` | 0.6 | Nao |

### Campos Ponderados (Recibo)

| Campo | Peso | Obrigatorio |
|-------|------|-------------|
| `normalized_cpf` | 1.0 | Sim |
| `taxpayer_name` | 1.0 | Sim |
| `exercise_year` | 0.9 | Sim |
| `calendar_year` | 0.8 | Nao |
| `transmission_datetime` | 0.8 | Nao |
| `receipt_number` | 0.7 | Nao |
| `tax_refund` / `tax_due` | 0.6 | Nao |

### Penalidades e Bonus

| Tipo | Ajuste | Condicao |
|------|--------|----------|
| Penalidade OCR | -10% | Documento processado via OCR |
| Penalidade Mixed | -5% | Documento com paginas mistas |
| Cap OCR Quality | Limitado | Confianca nao ultrapassa OCR confidence |
| Bonus Email | +2% | Declaracao com email valido |
| Bonus Restituicao Completa | +3% | Recibo com dados bancarios/PIX completos |

### Exemplo de Uso

```python
from irpf_processor.domain.services import ConfidenceCalculatorFactory
from irpf_processor.domain.enums import DocumentCategory

calculator = ConfidenceCalculatorFactory.get_calculator(
    document_category=DocumentCategory.DECLARACAO,
    extraction_method="digital"
)

result = calculator.calculate(extracted_data=my_data)

print(f"Confianca: {result.overall * 100:.1f}%")
print(f"Nivel: {result.level_pt}")  # excelente, boa, media, baixa
print(f"Campos encontrados: {result.details['fields_found']}")
print(f"Penalidades: {result.penalties}")
print(f"Bonus: {result.bonuses}")
```

### Metricas Grafana

O sistema exporta metricas detalhadas para o Grafana:

```promql
# Distribuicao por nivel de confianca
sum by (confidence_level) (irpf_confidence_by_level_total)

# Media de campos extraidos
avg(irpf_confidence_fields_found)

# Penalidades aplicadas
sum by (penalty_type) (irpf_confidence_penalties_applied_total)

# Bonus aplicados
sum by (bonus_type) (irpf_confidence_bonuses_applied_total)
```

### Reprocessar Documentos Existentes

Para recalcular a confianca de documentos ja processados com o novo algoritmo:

```bash
# Dry-run (apenas mostra mudancas)
python scripts/reprocess_confidence.py --tenant meu-tenant

# Executar alteracoes
python scripts/reprocess_confidence.py --tenant meu-tenant --execute

# Todos os tenants
python scripts/reprocess_confidence.py --execute
```

---

## 🧪 Testes

### Metricas de Cobertura

| Metrica | Valor |
|---------|-------|
| **Cobertura Total** | 85.29% |
| **Testes Passando** | 872 |
| **Threshold Minimo** | 85% |

### Estrutura de Testes

```
tests/
├── unit/                    # Testes unitarios (sem I/O)
│   ├── workers/             # Workers (extraction, ocr, router, broker)
│   ├── persistence/         # Repositories (document, api_key, database, redis)
│   ├── storage/             # MinIO storage
│   ├── extractors/          # Extractors (taxpayer, assets)
│   ├── api/                 # Auth dependencies, routes (documents)
│   ├── ocr/                 # OCR modules (tesseract, docling, orchestrator, preprocessor)
│   ├── shared/              # Metrics, tracing, instrumentation
│   ├── test_receipt_parser.py
│   ├── test_version_detector.py
│   └── test_config.py
├── integration/             # Testes de integracao
└── e2e/                     # Testes end-to-end
```

### Executar Testes

```bash
# Usando o script padronizado
./scripts/run_tests.sh unit          # Testes unitarios
./scripts/run_tests.sh integration   # Testes de integracao
./scripts/run_tests.sh e2e           # Testes end-to-end
./scripts/run_tests.sh all           # Todos os testes
./scripts/run_tests.sh docker        # Testes em container

# Ou diretamente com pytest
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/e2e/ -v -m e2e

# Com cobertura
pytest tests/ --cov=src/irpf_processor --cov-report=html
open htmlcov/index.html
```

### Testes em Docker (Recomendado)

O projeto inclui um `docker-compose.test.yml` dedicado para testes com Python 3.11:

```bash
# Executar testes unitarios
docker compose -f docker-compose.test.yml run --rm test-unit

# Executar testes de integracao
docker compose -f docker-compose.test.yml run --rm test-integration

# Executar todos os testes com cobertura
docker compose -f docker-compose.test.yml run --rm test-runner \
  pytest tests/unit/ --cov=src --cov-report=term -q
```

### Cobertura por Modulo

| Modulo | Testes | Cobertura |
|--------|--------|-----------|
| **Workers** | 45+ | extraction, ocr, router, broker |
| **OCR** | 60+ | tesseract, docling, orchestrator, preprocessor |
| **Persistence** | 50+ | document_repo, api_key_repo, database, redis |
| **Storage** | 17 | minio_storage |
| **Extractors** | 46 | taxpayer, assets |
| **API** | 70+ | auth dependencies, documents routes |
| **Shared** | 80+ | metrics (100%), tracing, instrumentation |
| **Parsers** | 57 | receipt, version_detector |

---

## 🔄 CI/CD Pipeline

O projeto possui um pipeline CI/CD completo em `.github/workflows/ci.yml` com GitHub Actions.

### Arquitetura do Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                        Push / Pull Request                       │
└─────────────────────────┬───────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
   ┌─────────┐      ┌──────────┐     ┌──────────────┐
   │  Lint   │      │Test Unit │     │Security Scan │
   │  (Ruff) │      │(872 tests)│    │(Bandit+Safety)│
   └────┬────┘      └─────┬────┘     └──────────────┘
        │                 │
        └────────┬────────┘
                 ▼
        ┌────────────────┐
        │Test Integration│
        │(MongoDB/Redis) │
        └───────┬────────┘
                │
        ┌───────┴───────┐
        ▼               ▼
   ┌─────────┐   ┌───────────┐
   │Coverage │   │Docker Build│
   │ Check   │   │ API+Worker │
   │  (85%)  │   └───────────┘
   └─────────┘
```

### Jobs do Pipeline

| Job | Descricao | Triggers |
|-----|-----------|----------|
| **lint** | Ruff check + format verification | Push, PR |
| **test-unit** | 872 testes unitarios com coverage XML | Push, PR |
| **test-integration** | Testes com services reais (MongoDB, Redis, MinIO) | Apos lint e unit |
| **coverage-check** | Verificacao do threshold 85% | Apos unit tests |
| **security-check** | Bandit (SAST) + Safety (dependencies) | Push, PR |
| **build** | Docker build multi-stage (API + Worker) | Push main/develop |

### Configuracao do Pipeline

```yaml
name: CI

on:
  push:
    branches: [main, develop, 'feature/**']
    paths-ignore: ['**.md', 'docs/**', 'infrastructure/**']
  pull_request:
    branches: [main, develop]

env:
  PYTHON_VERSION: '3.11'
```

### Services de Integracao

O pipeline `test-integration` sobe services reais via GitHub Actions:

| Service | Imagem | Porta |
|---------|--------|-------|
| MongoDB | mongo:6.0 | 27017 |
| Redis | redis:7.0-alpine | 6379 |
| MinIO | minio/minio | 9000 |

### Coverage Reports

- **Codecov**: Upload automatico para codecov.io
- **HTML Report**: Disponivel como artifact no GitHub
- **Terminal**: Exibido nos logs do CI

### Badges

```markdown
![Tests](https://github.com/AsaBank/asa-nfe-process/actions/workflows/ci.yml/badge.svg)
![Coverage](https://codecov.io/gh/AsaBank/asa-nfe-process/branch/main/graph/badge.svg)
```

### Security Scanning

| Ferramenta | Tipo | Descricao |
|------------|------|-----------|
| **Bandit** | SAST | Analise estatica de seguranca Python |
| **Safety** | SCA | Verificacao de vulnerabilidades em dependencias |

---

## 🧪 Testes E2E (End-to-End)

Os testes E2E validam o fluxo completo da aplicacao com infraestrutura real.

```bash
# 1. Subir infraestrutura
docker compose up -d

# 2. Criar API Key para testes
python -m irpf_processor.cli.create_api_key \
  --tenant-id e2e-test \
  --name "E2E Test Key" \
  --admin

# 3. Exportar API Key e rodar testes
export E2E_API_KEY="irpf_ak_xxxxx"
python scripts/run_e2e_tests.py

# Ou diretamente com pytest
pytest tests/e2e/ -v -m e2e
```

### Cenarios de Teste E2E

| Cenario | Descricao |
|---------|-----------|
| Health Check | Verifica /health, /ready, /metrics |
| Document Upload | Upload, status, processamento, resultado |
| Search | Busca por CPF, filtros, paginacao |
| Authentication | Endpoints protegidos, validacao de scopes |

### Teste do Parser com Massa de Dados

```bash
# Gerar 50 PDFs sinteticos e testar
python -m irpf_processor.cli.generate_test_models --test --max-tests 50
```

### Comandos Uteis

```bash
# Lint e formatacao
./scripts/run_tests.sh lint

# Limpar cache de testes
./scripts/run_tests.sh clean

# Gerar relatorio de cobertura
./scripts/run_tests.sh coverage
```

---

## 🏗️ Arquitetura

### Visão Geral

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────────────────┐
│   Cliente   │────▶│  API :8000  │────▶│          Workers            │
└─────────────┘     └──────┬──────┘     │  ┌─────────┐ ┌───────────┐  │
                           │            │  │ Router  │ │  Digital  │  │
                    ┌──────┴──────┐     │  └────┬────┘ └─────┬─────┘  │
                    ▼             ▼     │       │            │        │
               ┌────────┐   ┌────────┐  │  ┌────┴────────────┴────┐   │
               │MongoDB │   │ Redis  │  │  │      OCR Worker      │   │
               └────────┘   └────────┘  │  │ (Tesseract + Docling)│   │
                    ▲                   │  └──────────────────────┘   │
                    │                   └─────────────────────────────┘
               ┌────────┐                          │
               │ MinIO  │◀─────────────────────────┘
               └────────┘
                    │
               ┌────────┐
               │ Jaeger │◀── Distributed Tracing
               └────────┘
```

### Clean Architecture

```
src/irpf_processor/
├── domain/              # Entidades, Enums, Exceptions
│   └── entities/
│       ├── document.py
│       └── api_key.py   # Autenticação
├── application/         # Use Cases, Services, Interfaces
│   ├── services/
│   │   ├── document_service.py
│   │   └── auth_service.py
│   └── interfaces/
├── infrastructure/
│   ├── extraction/      # Parser IRPF + Extractors
│   │   └── ocr/         # Tesseract, Docling, Orchestrator
│   ├── persistence/     # MongoDB Repositories
│   └── storage/         # MinIO Service
├── presentation/
│   ├── api/             # FastAPI Routes
│   │   ├── routes/
│   │   │   ├── documents.py
│   │   │   ├── search.py
│   │   │   └── auth.py  # Endpoints de autenticação
│   │   └── dependencies/
│   │       └── auth.py  # Middleware de autenticação
│   └── workers/         # Dramatiq Workers
├── shared/              # Logging, Metrics, Tracing
│   ├── logging.py
│   ├── metrics.py
│   ├── tracing.py       # OpenTelemetry
│   └── instrumentation.py
├── templates/           # YAML definitions (2023-2025)
└── cli/                 # Ferramentas CLI
    └── create_api_key.py
```

### Documentacao Completa

- [Arquitetura Detalhada](docs/architecture/OVERVIEW.md)

---

## 🔐 DevSecOps & Infrastructure as Code

O projeto possui infraestrutura completa como codigo (IaC) usando **Terraform** para deploy em **Azure** ou **GCP**.

### Arquitetura Cloud (Azure)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Azure Resource Group                                │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        Virtual Network (VNet)                          │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │ │
│  │  │  Container   │  │   Database   │  │    Cache     │  │  Private   │ │ │
│  │  │ Apps Subnet  │  │    Subnet    │  │   Subnet     │  │ Endpoints  │ │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │              Azure Container Apps Environment                         │   │
│  │  ┌─────────┐  ┌───────────────┐  ┌───────────────┐  ┌─────────────┐  │   │
│  │  │   API   │  │ Worker Router │  │Worker Digital │  │ Worker OCR  │  │   │
│  │  │  :8000  │  │               │  │               │  │             │  │   │
│  │  └─────────┘  └───────────────┘  └───────────────┘  └─────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────────────────┐ │
│  │ Cosmos DB  │  │   Azure    │  │   Azure    │  │  Azure Container      │ │
│  │ (MongoDB)  │  │   Redis    │  │   Blob     │  │     Registry          │ │
│  └────────────┘  └────────────┘  └────────────┘  └────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │            Azure Monitor  +  Log Analytics  +  Application Insights     ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────────┘
```

### Mapeamento Local para Cloud

| Local (Docker Compose) | Azure Cloud | Funcao |
|------------------------|-------------|--------|
| MongoDB | Cosmos DB (MongoDB API) | Persistencia |
| Redis | Azure Cache for Redis | Filas Dramatiq |
| MinIO | Azure Blob Storage | PDFs |
| Prometheus/Grafana | Azure Monitor | Metricas |
| Jaeger | Application Insights | Tracing |
| Docker Containers | Azure Container Apps | Runtime |
| - | Azure Container Registry | Imagens |
| - | Virtual Network | Isolamento |
| - | Private Endpoints | Seguranca |

### Estrutura Terraform

```
infrastructure/terraform/
├── main.tf                      # Orquestracao dos modulos
├── variables.tf                 # Variaveis de entrada
├── outputs.tf                   # URLs e connection strings
├── versions.tf                  # Providers (azurerm)
├── backend.tf                   # State remoto (Azure Blob)
│
├── modules/
│   ├── networking/              # VNet, Subnets, NSGs, Private DNS
│   ├── database/                # Cosmos DB (MongoDB API)
│   ├── cache/                   # Azure Cache for Redis
│   ├── storage/                 # Azure Blob Storage
│   ├── containers/              # Container Apps + ACR
│   └── observability/           # Log Analytics + App Insights
│
├── environments/
│   ├── dev/                     # Config minimalista
│   ├── staging/                 # Config intermediaria
│   └── prod/                    # Config robusta + HA
│
└── scripts/
    ├── bootstrap.sh             # Cria storage para state
    ├── deploy.sh                # Deploy interativo
    ├── destroy.sh               # Destruir ambiente
    └── push-images.sh           # Build + push imagens
```

### Deploy Rapido

```bash
cd infrastructure/terraform/scripts

./bootstrap.sh

./deploy.sh dev

./push-images.sh dev v1.0.0
```

### Recursos por Ambiente

| Recurso | Dev | Staging | Prod |
|---------|-----|---------|------|
| API CPU | 0.25 cores | 0.5 cores | 1.0 cores |
| API Memory | 0.5 Gi | 1 Gi | 2 Gi |
| API Replicas | 1-3 | 2-5 | 3-10 |
| Worker CPU | 0.5 cores | 1.0 cores | 2.0 cores |
| Worker Memory | 1 Gi | 2 Gi | 4 Gi |
| Redis SKU | Basic/C0 | Standard/C1 | Premium/P1 |
| ACR SKU | Basic | Standard | Premium |

### Seguranca (Security-First)

| Controle | Implementacao |
|----------|---------------|
| Network Isolation | VNet com subnets segregadas |
| Private Connectivity | Private Endpoints para todos os servicos |
| No Public Access | Cosmos DB, Redis, Storage sem acesso publico |
| TLS | Minimo TLS 1.2 em todos os servicos |
| Secrets Management | Azure Container Apps Secrets |
| RBAC | Managed Identities (futuro) |

### CI/CD Pipeline (GitHub Actions)

```yaml
name: Terraform
on:
  push:
    branches: [main]
    paths: ['infrastructure/terraform/**']

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: hashicorp/setup-terraform@v3
      - run: terraform fmt -check -recursive
      - run: terraform validate

  deploy-dev:
    needs: validate
    environment: dev
    steps:
      - run: terraform apply -auto-approve
```

### Custos Estimados (Brazil South)

| Ambiente | Custo Mensal Estimado |
|----------|----------------------|
| Dev | R$ 500 - 800 |
| Staging | R$ 1.500 - 2.500 |
| Prod | R$ 4.000 - 8.000 |

### Opcoes de Cloud

O projeto suporta duas clouds:

| Cloud | Diretorio | Database | Containers | Vantagens |
|-------|-----------|----------|------------|-----------|
| **Azure** | `infrastructure/terraform/` | Cosmos DB (nativo) | Container Apps | Integracao nativa MongoDB API |
| **GCP** | `infrastructure/terraform-gcp/` | MongoDB Atlas | Cloud Run | Menor custo no Brasil |

### Deploy Rapido - GCP

```bash
cd infrastructure/terraform-gcp/scripts

./bootstrap.sh <project-id>

export TF_VAR_project_id="project-id"
export TF_VAR_mongodb_atlas_public_key="xxx"
export TF_VAR_mongodb_atlas_private_key="xxx"
export TF_VAR_mongodb_atlas_org_id="xxx"

./deploy.sh dev

./push-images.sh dev v1.0.0
```

### Documentacao Terraform

- [Terraform Azure README](infrastructure/terraform/README.md)
- [Terraform GCP README](infrastructure/terraform-gcp/README.md)
- [Azure Container Apps](https://learn.microsoft.com/azure/container-apps/)
- [GCP Cloud Run](https://cloud.google.com/run/docs)

---

## 📊 Observabilidade

### Stack de Observabilidade

| Pilar | Tecnologia | URL |
|-------|------------|-----|
| **Métricas** | Prometheus + Grafana | http://localhost:3000 |
| **Logs** | Structlog (JSON) | `docker compose logs` |
| **Tracing** | OpenTelemetry + Jaeger | http://localhost:16686 |

### Acessar Dashboards

| Serviço | URL | Credenciais |
|---------|-----|-------------|
| **Grafana** | http://localhost:3000 | admin / admin |
| **Prometheus** | http://localhost:9095 | - |
| **Jaeger** | http://localhost:16686 | - |
| **MinIO Console** | http://localhost:9001 | minioadmin / minioadmin |

### Métricas Prometheus

```promql
# Total de documentos processados
sum(irpf_documents_processed_total)

# Por tipo de PDF
sum by (pdf_type) (irpf_documents_processed_total)

# Tempo médio de extração (P95)
histogram_quantile(0.95, irpf_extraction_duration_seconds_bucket)

# OCR: Total de operações por engine
sum by (ocr_engine) (irpf_ocr_usage_total)

# Taxa de sucesso
irpf_documents_processed_total{status="READY"} / irpf_documents_processed_total
```

### Distributed Tracing (OpenTelemetry)

O sistema possui tracing distribuído para rastreamento de requisições end-to-end.

**Como funciona:**

1. API recebe requisição e inicia um span pai
2. Trace ID é propagado para workers via mensagens Dramatiq
3. Workers criam spans filhos mantendo o contexto
4. Logs incluem `trace_id` e `span_id` automaticamente
5. Response headers incluem `X-Trace-ID` para correlação

**Buscar traces no Jaeger:**

1. Acesse http://localhost:16686
2. Selecione o serviço `irpf-processor-api` ou `irpf-processor-worker`
3. Filtre por operation, tags ou trace ID
4. Visualize o fluxo completo da requisição

### Grafana Dashboard

O dashboard **IRPF Processor - Analytics Dashboard** oferece visibilidade completa do sistema.

**Acesso:** http://localhost:3000 (admin / admin)

#### Secoes do Dashboard

| Secao | Paineis | Descricao |
|-------|---------|-----------|
| **Overview - KPIs Principais** | 6 | Total Uploads, Processados OK, Falhas, Taxa de Sucesso, Confianca Media |
| **Volume e Throughput** | 2 | Taxa de Upload vs Processamento, Documentos por Status (Timeline) |
| **Performance e Latencia** | 2 | Tempo de Processamento (Percentis), Tempo por Tipo de PDF |
| **Qualidade da Extracao** | 2 | Distribuicao de Confianca por Faixa, Confianca por Tipo de Documento |
| **OCR - PDFs Escaneados** | 4 | Total OCR, Tempo OCR, Confianca OCR por Faixa, Taxa de Sucesso OCR |
| **Distribuicao por Dimensoes** | 4 | Por Tipo PDF, Por Categoria, Por Ano-Exercicio, Por Tenant |
| **Perfil das Declaracoes** | 2 | Secoes Preenchidas, Secoes Vazias |
| **Qualidade e Revisao** | 3 | Documentos por Nivel de Confianca, Processados via OCR, Alertas |
| **API e Infraestrutura** | 3 | Requisicoes por Endpoint, Latencia API, Jobs em Fila |
| **Storage e Database** | 2 | Operacoes MinIO, Operacoes MongoDB |
| **Tamanho de PDFs** | 2 | Distribuicao de Tamanho, Distribuicao de Paginas |

#### Metricas Principais

```promql
# KPIs
sum(irpf_documents_uploaded_total)                    # Total uploads
sum(irpf_documents_processed_total{status="READY"})   # Processados OK
avg(irpf_extraction_confidence_sum / irpf_extraction_confidence_count)  # Confianca media

# Distribuicao por Tipo
sum by (pdf_type) (irpf_documents_by_pdf_type_total)  # DIGITAL vs IMAGE
sum by (category) (irpf_documents_by_category_total)  # DECLARACAO vs RECIBO

# Confianca
sum by (confidence_level) (irpf_confidence_by_level_total)  # excellent, good, medium, low

# OCR
sum by (ocr_engine) (irpf_ocr_usage_total)            # Tesseract vs Docling
histogram_quantile(0.95, irpf_ocr_duration_seconds_bucket)  # P95 tempo OCR
```

#### Secao Qualidade e Revisao

Esta secao mostra informacoes acionaveis para revisao de documentos:

| Painel | Descricao | O que observar |
|--------|-----------|----------------|
| **Documentos por Nivel de Confianca** | Distribuicao Baixa/Media/Boa/Excelente | Muitos em Baixa = problema |
| **Documentos Processados via OCR** | Quantidade de PDFs escaneados | Informativo |
| **Alertas** | Falhas + Documentos para revisao manual | Vermelho = atencao necessaria |

#### Reset de Metricas

Para resetar todas as metricas do Grafana e recomecar:

```bash
./scripts/reset_metrics.sh
```

Este script:
1. Para e remove os containers Prometheus, Pushgateway e Grafana
2. Remove os volumes de dados
3. Limpa os dados do MongoDB do tenant especificado
4. Reinicia todos os servicos
5. Verifica se as metricas foram zeradas

---

## 🐛 Troubleshooting

### Container não inicia

```bash
# Verificar logs
docker compose logs api
docker compose logs worker-router worker-digital worker-ocr

# Reiniciar serviços
docker compose restart api worker-router worker-digital worker-ocr
```

### Worker não processa documentos

```bash
# Verificar se Redis está rodando
docker compose exec redis redis-cli ping

# Verificar filas
docker compose exec redis redis-cli LLEN dramatiq:extraction-router
docker compose exec redis redis-cli LLEN dramatiq:default
docker compose exec redis redis-cli LLEN dramatiq:extraction-ocr
```

### Documento fica em RECEIVED

```bash
# Verificar logs do router
docker compose logs -f worker-router

# Verificar status no MongoDB
docker compose exec mongo mongosh irpf_processor --eval \
  'db.documents.findOne({document_id: "SEU_ID"}, {status: 1, pdf_type: 1})'
```

### Erro de autenticação (401/403)

```bash
# Verificar se a API Key existe
docker compose exec mongo mongosh irpf_processor --eval \
  'db.api_keys.find({tenant_id: "seu-tenant"}).pretty()'

# Criar nova API Key
python -m irpf_processor.cli.create_api_key \
  --tenant-id seu-tenant \
  --name "Nova Key" \
  --admin
```

### Traces não aparecem no Jaeger

```bash
# Verificar se Jaeger está rodando
curl http://localhost:16686

# Verificar variáveis de ambiente
docker compose exec api env | grep OTEL

# Reiniciar com tracing habilitado
docker compose restart api worker-router worker-digital worker-ocr
```

### Limpar dados e recomeçar

```bash
# CUIDADO: Remove todos os dados!
docker compose down -v
docker compose up -d
```

---

## 📦 Gerenciamento de Dependências

### Dependências Travadas

O projeto usa `requirements.lock` para builds reproduzíveis:

```bash
# Instalar dependências travadas (produção)
pip install -r requirements.lock

# Instalar em modo desenvolvimento
pip install -e ".[dev]"
```

### Atualizar Dependências

```bash
# Atualizar requirements.lock
./scripts/update_deps_lock.sh

# Testar localmente
pip install -r requirements.lock

# Commit
git add requirements.lock
git commit -m "chore(deps): update locked dependencies"
```

---

## 📝 Convenções de Código

### Regras

1. **Sem comentários inline** - Código autodocumentável
2. **Type hints obrigatórios** - Em todas as funções públicas
3. **Logs estruturados** - Usar `structlog` com `correlation_id`
4. **Testes para tudo** - Mínimo 80% de cobertura

### Commits

```
feat: adiciona extrator de criptoativos
fix: corrige parsing de valores negativos
docs: atualiza README com novos endpoints
test: adiciona testes para rural_assets_extractor
chore: atualiza dependências
```

---

## 🤝 Contribuindo

1. Crie uma branch: `git checkout -b feature/minha-feature`
2. Faça suas alterações
3. Execute os testes: `pytest tests/ -v`
4. Commit: `git commit -m "feat: minha feature"`
5. Push: `git push origin feature/minha-feature`
6. Abra um Pull Request

---

## 📞 Suporte

- **Documentação:** [docs/architecture/OVERVIEW.md](docs/architecture/OVERVIEW.md)
- **Issues:** GitHub Issues
- **Slack:** #irpf-processor

---

<div align="center">

**Feito com ❤️ por Felipe Scaphe para o AsaBank**

*Janeiro 2026*

</div>
