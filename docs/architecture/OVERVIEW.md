# 🏛️ IRPF Processor — Visão Geral da Arquitetura

**Versão:** 3.0  
**Data:** 2026-01-17  
**Status:** Production Ready

---

## 📈 Métricas do Projeto

| Categoria | Métrica | Valor |
|-----------|---------|-------|
| 📝 **Código** | Linhas de código | ~12,000 |
| 📝 **Código** | Arquivos Python | ~95 |
| 📝 **Código** | Templates YAML | 3 |
| 🧪 **Testes** | Testes unitários | 366 |
| 🧪 **Testes** | Testes E2E | 36 |
| 🧪 **Testes** | Cobertura alvo | >80% |
| 📄 **Extração** | Extratores de seção | 10 |
| 📄 **Extração** | Versões suportadas | 3 (2023-2025) |
| 📄 **Extração** | Campos extraídos | 50+ |
| 🔒 **Segurança** | Autenticação | API Key (M2M) |
| 🔒 **Segurança** | Scopes | 4 |
| 📊 **Observabilidade** | Métricas | Prometheus |
| 📊 **Observabilidade** | Tracing | OpenTelemetry + Jaeger |

---

## 📊 Dashboard de Status

| Feature | Status |
|---------|--------|
| API REST (FastAPI) | ✅ Implementado |
| Upload de Documentos | ✅ Implementado |
| Workers Dramatiq (3 tipos) | ✅ Implementado |
| MongoDB + Redis + MinIO | ✅ Implementado |
| Parser IRPF (10 extratores) | ✅ Implementado |
| Detecção de Versão (2023-2025) | ✅ Implementado |
| Sistema de Templates YAML | ✅ Implementado |
| Search API (CPF, Ano, Cidade) | ✅ Implementado |
| **OCR Dual-Engine** | ✅ Implementado |
| **Autenticação API Key** | ✅ Implementado |
| **Multi-tenancy** | ✅ Implementado |
| **Distributed Tracing** | ✅ Implementado |
| **Testes E2E Automatizados** | ✅ Implementado |
| Prometheus + Grafana + Jaeger | ✅ Implementado |
| SSE Events | ⏳ Pendente |

---

## 1. Arquitetura de Alto Nível

```mermaid
flowchart TB
    subgraph Clients["🌐 Clients"]
        Postman[Postman]
        Frontend[Frontend<br/>Vue/React]
        ERP[ERP Systems]
        Swagger[Swagger UI]
    end

    subgraph Gateway["🔐 Security Layer"]
        Auth[API Key<br/>Authentication]
        Tenant[Multi-tenant<br/>Isolation]
    end

    subgraph API["📡 API Service :8000"]
        direction TB
        Upload[POST /v1/documents]
        Status[GET /status]
        Search[GET /search]
        AuthAPI[/v1/auth/*]
        Health[GET /health]
        Metrics[GET /metrics]
    end

    subgraph Workers["👷 Worker Services"]
        direction TB
        RouterW[Router Worker<br/>extraction-router]
        DigitalW[Digital Worker<br/>default queue]
        OCRW[OCR Worker<br/>extraction-ocr]
    end

    subgraph OCR["🔍 OCR Engines"]
        Tesseract[Tesseract<br/>~30s]
        Docling[Docling IBM<br/>~200s fallback]
    end

    subgraph Infra["🏗️ Infrastructure"]
        MongoDB[(MongoDB<br/>:27017)]
        Redis[(Redis<br/>:6379)]
        MinIO[(MinIO<br/>:9000)]
    end

    subgraph Observability["📊 Observability Stack"]
        Prometheus[Prometheus<br/>:9095]
        Grafana[Grafana<br/>:3000]
        Jaeger[Jaeger<br/>:16686]
        Pushgateway[Pushgateway<br/>:9091]
    end

    Clients --> Gateway
    Gateway --> API
    API --> MongoDB
    API --> Redis
    API --> MinIO
    API -.->|Enqueue| Workers
    
    RouterW -->|DIGITAL| DigitalW
    RouterW -->|IMAGE/MIXED| OCRW
    OCRW --> Tesseract
    OCRW -.->|fallback| Docling
    
    Workers --> MongoDB
    Workers --> MinIO
    Workers --> Pushgateway
    
    API -.->|traces| Jaeger
    Workers -.->|traces| Jaeger
    Prometheus -->|Scrape| API
    Prometheus -->|Scrape| Pushgateway
    Grafana --> Prometheus
    Grafana --> Jaeger
```

---

## 2. Fluxo de Processamento de Documento

```mermaid
sequenceDiagram
    autonumber
    participant C as Cliente
    participant Auth as Auth Layer
    participant API as API Service
    participant S3 as MinIO
    participant DB as MongoDB
    participant Q as Redis Queue
    participant Router as Router Worker
    participant Digital as Digital Worker
    participant OCR as OCR Worker
    participant Jaeger as Jaeger

    Note over C,Jaeger: 🔐 FASE 0: Autenticação
    C->>+Auth: Authorization: Bearer API_KEY
    Auth->>Auth: Validar API Key + Scopes
    Auth->>Auth: Verificar Tenant
    Auth-->>-C: ✓ Authorized

    Note over C,Jaeger: 📤 FASE 1: Upload (~100ms)
    C->>+API: POST /v1/documents
    API->>Jaeger: Start Trace (trace_id)
    API->>API: Calcular SHA256
    API->>S3: Upload PDF
    S3-->>API: storage_uri
    API->>DB: Insert (status: RECEIVED)
    API->>Q: Enqueue job (+ trace_context)
    API-->>-C: 202 Accepted + X-Trace-ID

    Note over C,Jaeger: 🔀 FASE 2: Routing (~50ms)
    Q->>+Router: Consume job
    Router->>Jaeger: Continue Trace
    Router->>S3: Download PDF
    Router->>Router: Detect PDF type
    Router->>DB: Update (status: ROUTED)
    
    alt PDF DIGITAL
        Router->>Q: Enqueue → Digital Worker
    else PDF IMAGE/MIXED
        Router->>Q: Enqueue → OCR Worker
    end
    Router-->>-Q: Job complete

    Note over C,Jaeger: 📄 FASE 3: Extraction
    alt Digital Path (~0.5s)
        Q->>+Digital: Consume job
        Digital->>Digital: pdfplumber extract
        Digital->>DB: Save results
        Digital-->>-Q: Complete
    else OCR Path (~30-200s)
        Q->>+OCR: Consume job
        OCR->>OCR: 1º Tesseract
        alt Tesseract < 50%
            OCR->>OCR: 2º Docling fallback
        end
        OCR->>DB: Save results
        OCR-->>-Q: Complete
    end

    Note over C,Jaeger: 🎯 FASE 4: Consulta
    C->>+API: GET /v1/documents/{id}
    API->>DB: Get extraction_result
    API-->>-C: 200 JSON Result
```

---

## 3. Stack Tecnológica

```mermaid
mindmap
  root((IRPF Processor))
    Application
      Python 3.11+
      FastAPI
      Dramatiq
      Uvicorn
    Extraction
      pdfplumber
      PyMuPDF
      Tesseract OCR
      Docling IBM
    Data
      MongoDB 7
      Redis 7
      MinIO S3
    Security
      API Key Auth
      Scopes/RBAC
      Multi-tenant
    Observability
      Prometheus
      Grafana
      OpenTelemetry
      Jaeger
      Structlog
    Validation
      Pydantic v2
      CPF/CNPJ
      Currency
```

---

## 4. Arquitetura de Camadas (Clean Architecture)

```mermaid
flowchart TB
    subgraph Presentation["📡 Presentation Layer"]
        Routes[API Routes<br/>FastAPI]
        AuthDeps[Auth Dependencies]
        Workers[Workers<br/>Dramatiq]
    end

    subgraph Application["🔄 Application Layer"]
        UseCases[Use Cases]
        Services[Services]
        AuthService[Auth Service]
        Interfaces[Interfaces]
        DTOs[DTOs]
    end

    subgraph Domain["🎯 Domain Layer"]
        Entities[Entities]
        ApiKey[ApiKey Entity]
        ValueObjects[Value Objects]
        Enums[Enums + Scopes]
        Exceptions[Exceptions]
    end

    subgraph Infrastructure["🏗️ Infrastructure Layer"]
        MongoDB_Repo[MongoDB Repository]
        ApiKey_Repo[ApiKey Repository]
        MinIO_Storage[MinIO Storage]
        Redis_Events[Redis Events]
        Extraction[IRPF Parser]
        OCR[OCR Engines]
        Templates[YAML Templates]
        Tracing[OpenTelemetry]
    end

    Presentation --> Application
    Application --> Domain
    Infrastructure -.->|implements| Application
    Infrastructure --> Domain
```

---

## 5. Estrutura de Pastas

```
src/irpf_processor/
├── main.py                          # FastAPI entrypoint
├── config.py                        # Pydantic Settings
│
├── domain/                          # 🎯 DOMAIN LAYER
│   ├── entities/
│   │   ├── document.py
│   │   └── api_key.py              # 🔐 API Key entity
│   ├── enums/
│   │   ├── document_status.py
│   │   ├── pdf_type.py
│   │   └── auth_scope.py           # 🔐 Scopes enum
│   ├── exceptions/
│   │   ├── domain_exceptions.py
│   │   └── auth_exceptions.py      # 🔐 Auth exceptions
│   └── value_objects/
│
├── application/                     # 🔄 APPLICATION LAYER
│   ├── interfaces/
│   │   ├── repositories.py
│   │   ├── event_publisher.py
│   │   └── auth_repository.py      # 🔐 Auth interface
│   ├── services/
│   │   ├── document_service.py
│   │   └── auth_service.py         # 🔐 Auth service
│   └── dto/
│
├── infrastructure/                  # 🏗️ INFRASTRUCTURE LAYER
│   ├── persistence/
│   │   ├── document_repository.py
│   │   ├── api_key_repository.py   # 🔐 API Key repo
│   │   └── database.py
│   ├── storage/minio_storage.py
│   └── extraction/
│       ├── irpf_parser.py          # Facade
│       ├── version_detector.py
│       ├── text_extractor.py
│       ├── table_extractor.py
│       ├── extractors/             # 10 Strategy extractors
│       └── ocr/                    # 🔍 OCR Engines
│           ├── tesseract_engine.py
│           ├── docling_engine.py
│           ├── ocr_orchestrator.py
│           └── pdf_type_detector.py
│
├── presentation/                    # 📡 PRESENTATION LAYER
│   ├── api/
│   │   ├── routes/
│   │   │   ├── documents.py
│   │   │   ├── search.py
│   │   │   ├── health.py
│   │   │   └── auth.py             # 🔐 Auth endpoints
│   │   └── dependencies/
│   │       └── auth.py             # 🔐 Auth middleware
│   └── workers/
│       ├── broker.py               # + OpenTelemetry middleware
│       ├── router_worker.py
│       ├── extraction_worker.py
│       └── ocr_worker.py
│
├── shared/                          # 🛠️ SHARED
│   ├── logging.py                  # Structlog + trace context
│   ├── metrics.py                  # Prometheus
│   ├── tracing.py                  # 📊 OpenTelemetry
│   └── instrumentation.py          # 📊 Auto-instrumentation
│
├── templates/definitions/           # 📋 YAML TEMPLATES
│   ├── irpf_2023.yaml
│   ├── irpf_2024.yaml
│   └── irpf_2025.yaml
│
└── cli/                             # 🛠️ CLI TOOLS
    ├── create_api_key.py           # 🔐 Bootstrap API Key
    ├── generate_test_models.py
    └── sync_layouts.py

tests/
├── unit/                            # Testes unitários
├── integration/                     # Testes de integração
└── e2e/                             # 🧪 Testes E2E
    ├── conftest.py
    ├── test_health.py
    ├── test_document_flow.py
    ├── test_search_flow.py
    └── test_auth_flow.py

scripts/
├── run_e2e_tests.py                # 🧪 Executor E2E
└── update_deps_lock.sh             # 📦 Lock dependencies
```

---

## 6. Sistema de Segurança

### 6.1 Arquitetura de Autenticação

```mermaid
sequenceDiagram
    participant C as Client
    participant API as FastAPI
    participant Dep as Auth Dependency
    participant Svc as AuthService
    participant DB as MongoDB

    C->>API: Request + Authorization: Bearer API_KEY
    API->>Dep: get_current_api_key()
    Dep->>Dep: Extract key from header
    Dep->>Svc: validate_api_key(key, tenant_id)
    Svc->>Svc: Hash key (SHA256)
    Svc->>DB: Find by prefix + hash
    DB-->>Svc: ApiKey entity
    Svc->>Svc: Check: active? expired? tenant?
    Svc->>DB: Update last_used_at
    Svc-->>Dep: Valid ApiKey
    Dep->>Dep: Check required scopes
    Dep-->>API: Authorized
    API-->>C: 200 OK
```

### 6.2 Scopes e Permissões

| Scope | Permissão | Endpoints |
|-------|-----------|-----------|
| `documents:write` | Upload de documentos | POST /v1/documents |
| `documents:read` | Consultar status/resultado | GET /v1/documents/* |
| `search:read` | Buscar declarações | GET /v1/irpf/search/* |
| `admin:keys` | Gerenciar API Keys | /v1/auth/keys/* |

### 6.3 Estrutura da API Key

```
irpf_ak_<random_48_chars>
   │
   └─ Prefixo identificador
   
Armazenamento:
- key_prefix: "irpf_ak_" (para lookup)
- key_hash: SHA256(full_key) (para validação)
```

---

## 7. Sistema OCR

### 7.1 Pipeline de Detecção e Roteamento

```mermaid
flowchart TB
    PDF[📄 PDF Input] --> Router[Router Worker]
    
    Router --> Detect{Detectar Tipo}
    Detect -->|has_text > 80%| Digital[DIGITAL]
    Detect -->|has_text < 20%| Image[IMAGE]
    Detect -->|20% < has_text < 80%| Mixed[MIXED]
    
    Digital --> DigitalQ[Queue: default]
    Image --> OCRQ[Queue: extraction-ocr]
    Mixed --> OCRQ
    
    DigitalQ --> DWorker[Digital Worker]
    OCRQ --> OCRWorker[OCR Worker]
    
    DWorker --> PDFPlumber[pdfplumber<br/>~0.5s]
    
    OCRWorker --> Tesseract[Tesseract<br/>~30s]
    Tesseract --> Check{Confidence<br/>≥ 50%?}
    Check -->|Yes| Result[Result]
    Check -->|No| Docling[Docling IBM<br/>~200s]
    Docling --> Result
    
    PDFPlumber --> Result
    Result --> DB[(MongoDB)]
```

### 7.2 Comparação de Engines

| Engine | Velocidade | Precisão | Uso |
|--------|------------|----------|-----|
| **pdfplumber** | ~0.5s | 95% | PDFs digitais |
| **Tesseract** | ~30s | 70% | OCR primário |
| **Docling** | ~200s | 72% | Fallback (tabelas complexas) |

---

## 8. Sistema de Observabilidade

### 8.1 Três Pilares

```mermaid
flowchart LR
    subgraph App["Application"]
        API[API]
        Workers[Workers]
    end

    subgraph Metrics["📊 Metrics"]
        Prometheus[(Prometheus)]
        Pushgateway[(Pushgateway)]
        Grafana[Grafana]
    end

    subgraph Logs["📝 Logs"]
        Structlog[Structlog<br/>JSON]
        Stdout[stdout/stderr]
    end

    subgraph Traces["🔍 Traces"]
        OTEL[OpenTelemetry<br/>SDK]
        Jaeger[(Jaeger)]
    end

    API -->|/metrics| Prometheus
    Workers -->|push| Pushgateway
    Pushgateway --> Prometheus
    Prometheus --> Grafana

    API --> Structlog
    Workers --> Structlog
    Structlog --> Stdout

    API --> OTEL
    Workers --> OTEL
    OTEL -->|OTLP| Jaeger
    Jaeger --> Grafana
```

### 8.2 Propagação de Contexto

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Redis
    participant Worker
    participant Jaeger

    Client->>API: Request
    API->>API: Create Span (trace_id: abc123)
    API->>Jaeger: Export Span
    API->>Redis: Enqueue Job<br/>options: {trace_context: {...}}
    API-->>Client: Response<br/>X-Trace-ID: abc123
    
    Redis->>Worker: Consume Job
    Worker->>Worker: Extract trace_context
    Worker->>Worker: Create Child Span<br/>(parent: abc123)
    Worker->>Jaeger: Export Span
    Worker->>Worker: set_correlation_id(trace_id)
    Note over Worker: Logs include trace_id
```

### 8.3 Métricas Disponíveis

| Métrica | Tipo | Labels |
|---------|------|--------|
| `irpf_documents_uploaded_total` | Counter | tenant_id |
| `irpf_documents_processed_total` | Counter | tenant_id, status, pdf_type |
| `irpf_extraction_duration_seconds` | Histogram | tenant_id, pdf_type, version |
| `irpf_ocr_usage_total` | Counter | tenant_id, ocr_engine |
| `irpf_ocr_duration_seconds` | Histogram | tenant_id, ocr_engine |
| `irpf_ocr_confidence` | Histogram | tenant_id, ocr_engine |
| `irpf_api_request_duration_seconds` | Histogram | method, endpoint, status_code |

---

## 9. Sistema de Parser IRPF

### 9.1 Arquitetura do Parser

```mermaid
flowchart TB
    subgraph Parser["IRPFParser (Facade)"]
        VD[VersionDetector]
        TE[TextExtractor<br/>pdfplumber]
        TB[TableExtractor<br/>pdfplumber]
    end

    subgraph Extractors["Section Extractors (Strategy Pattern)"]
        E1[TaxpayerExtractor]
        E2[AssetsExtractor]
        E3[IncomePJExtractor]
        E4[ExemptIncomeExtractor]
        E5[ExclusiveIncomeExtractor]
        E6[RuralPropertiesExtractor]
        E7[RuralIncomeExtractor]
        E8[RuralResultsExtractor]
        E9[RuralAssetsExtractor]
        E10[RuralDebtsExtractor]
    end

    subgraph Output["Output"]
        Result[IRPFDeclarationResult]
        Confidence[Confidence: 0.0 - 1.0]
        Warnings[Warnings: list]
    end

    PDF[📄 PDF Input] --> Parser
    Parser --> Extractors
    Extractors --> Output
```

### 9.2 Sistema de Templates YAML

```yaml
# templates/definitions/irpf_2025.yaml
metadata:
  version: "2025"
  exercise_year: "2025"
  calendar_year: "2024"

sections:
  taxpayer_identification:
    name: "Identificação do Contribuinte"
    required: true
    fields:
      - { name: cpf, type: cpf, required: true }
      - { name: name, type: string, required: true }
      
  assets_declaration:
    name: "Bens e Direitos"
    repeatable: true
    has_totals: true
```

---

## 10. Docker Compose Services

```mermaid
flowchart TB
    subgraph Docker["🐳 Docker Compose"]
        subgraph App["Application"]
            api[api :8000]
            router[worker-router]
            digital[worker-digital]
            ocr[worker-ocr]
        end
        
        subgraph Data["Data Stores"]
            mongo[(mongo :27017)]
            redis[(redis :6379)]
            minio[(minio :9000)]
        end
        
        subgraph Monitoring["Observability"]
            prometheus[prometheus :9095]
            pushgateway[pushgateway :9091]
            grafana[grafana :3000]
            jaeger[jaeger :16686]
        end
    end

    api --> mongo
    api --> redis
    api --> minio
    api --> jaeger
    
    router --> mongo
    router --> redis
    router --> minio
    router --> jaeger
    
    digital --> mongo
    digital --> minio
    digital --> pushgateway
    digital --> jaeger
    
    ocr --> mongo
    ocr --> minio
    ocr --> pushgateway
    ocr --> jaeger
    
    prometheus --> api
    prometheus --> pushgateway
    grafana --> prometheus
    grafana --> jaeger
```

---

## 11. Testes

### 11.1 Pirâmide de Testes

```mermaid
%%{init: {'theme': 'base'}}%%
pie title Distribuição de Testes
    "Unitários (366)" : 366
    "Integração (30)" : 30
    "E2E (36)" : 36
```

### 11.2 Cobertura por Componente

| Componente | Testes | Cobertura |
|------------|--------|-----------|
| Domain (Entities, Enums) | 45 | ~95% |
| Field Extractors | 62 | ~90% |
| Section Extractors | 85 | ~85% |
| Auth Service | 28 | ~90% |
| API Routes | 52 | ~85% |
| OCR Engines | 35 | ~80% |
| E2E Flows | 36 | Full paths |

### 11.3 Cenários E2E

| Cenário | Arquivo | Testes |
|---------|---------|--------|
| Health & Ready | test_health.py | 4 |
| Document Flow | test_document_flow.py | 9 |
| Search Flow | test_search_flow.py | 9 |
| Auth Flow | test_auth_flow.py | 14 |

---

## 12. Decisões Arquiteturais (ADRs)

### ADR-001: MongoDB como Document Store
| Aspecto | Detalhe |
|---------|---------|
| **Contexto** | Armazenar declarações IRPF com estrutura variável |
| **Decisão** | Usar MongoDB |
| **Justificativa** | Schema flexível, documentos JSON, motor async |

### ADR-002: API Key Authentication
| Aspecto | Detalhe |
|---------|---------|
| **Contexto** | Autenticação M2M para sistemas bancários |
| **Decisão** | API Key com scopes |
| **Justificativa** | Simples, stateless, multi-tenant, auditável |

### ADR-003: OpenTelemetry para Tracing
| Aspecto | Detalhe |
|---------|---------|
| **Contexto** | Rastrear requests através de API + Workers |
| **Decisão** | OpenTelemetry + Jaeger |
| **Justificativa** | Vendor-neutral, propagação automática, visualização |

### ADR-004: Dual OCR Engine
| Aspecto | Detalhe |
|---------|---------|
| **Contexto** | Extrair texto de PDFs escaneados |
| **Decisão** | Tesseract (primário) + Docling (fallback) |
| **Justificativa** | Balance velocidade/precisão, fallback automático |

### ADR-005: Dependências Travadas
| Aspecto | Detalhe |
|---------|---------|
| **Contexto** | Builds reproduzíveis em produção |
| **Decisão** | requirements.lock com versões fixas |
| **Justificativa** | Previsibilidade, segurança, CI/CD confiável |

---

## 13. Links Úteis

| Recurso | URL | Descrição |
|---------|-----|-----------|
| **API** | http://localhost:8000 | FastAPI REST API |
| **Swagger** | http://localhost:8000/docs | Documentação interativa |
| **ReDoc** | http://localhost:8000/redoc | Documentação alternativa |
| **Grafana** | http://localhost:3000 | Dashboards (admin/admin) |
| **Prometheus** | http://localhost:9095 | Queries de métricas |
| **Jaeger** | http://localhost:16686 | Distributed Tracing |
| **MinIO** | http://localhost:9001 | Object storage |

---

## 14. Comandos Essenciais

```bash
# Subir infraestrutura
docker compose up -d

# Ver logs
docker compose logs -f api worker-router worker-digital worker-ocr

# Testar health
curl http://localhost:8000/health

# Criar API Key admin
python -m irpf_processor.cli.create_api_key \
  --tenant-id meu-tenant \
  --name "Admin" \
  --admin

# Upload documento
curl -X POST http://localhost:8000/v1/documents \
  -H "X-Tenant-ID: meu-tenant" \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@documento.pdf"

# Buscar por CPF
curl "http://localhost:8000/v1/irpf/search/by-cpf/123.456.789-00" \
  -H "X-Tenant-ID: meu-tenant" \
  -H "Authorization: Bearer $API_KEY"

# Rodar testes E2E
export E2E_API_KEY="irpf_ak_xxxxx"
python scripts/run_e2e_tests.py

# Atualizar dependências
./scripts/update_deps_lock.sh
```

---

<div align="center">

**Feito por Felipe Scaphe com ❤️ para o AsaBank**

*Janeiro 2026*

---

### 📊 Estatísticas Finais

| Métrica | Valor |
|---------|-------|
| Linhas de código | ~12,000 |
| Testes automatizados | 432 |
| Extratores de seção | 10 |
| Templates YAML | 3 (2023-2025) |
| OCR Engines | 2 (Tesseract + Docling) |
| Scopes de segurança | 4 |
| Tempo médio (digital) | 0.5s |
| Tempo médio (OCR) | 30s |

</div>
