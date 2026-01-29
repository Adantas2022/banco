# Arquitetura de Observabilidade - IRPF Processor

## Visão Geral

O sistema IRPF Processor utiliza uma stack de observabilidade completa para monitoramento local e em produção.

---

## Componentes

### 1. OpenTelemetry SDK (Integrado na Aplicação)

**Não precisa instalar separadamente** - já está incluído como dependências Python.

```
opentelemetry-api>=1.22.0
opentelemetry-sdk>=1.22.0
opentelemetry-exporter-otlp>=1.22.0
opentelemetry-instrumentation-fastapi>=0.43b0
opentelemetry-instrumentation-httpx>=0.43b0
opentelemetry-instrumentation-pymongo>=0.43b0
opentelemetry-instrumentation-redis>=0.43b0
opentelemetry-instrumentation-logging>=0.43b0
```

**Função**: Coleta automaticamente traces e spans de:
- Requisições HTTP (FastAPI)
- Chamadas ao MongoDB
- Operações no Redis
- Logs estruturados

---

### 2. Jaeger (Container)

**Porta**: `16686` (UI) | `4317` (OTLP gRPC)

**Função**: Recebe e visualiza distributed traces.

**Acesso**: http://localhost:16686

---

### 3. Prometheus (Container)

**Porta**: `9095`

**Função**: Coleta métricas da aplicação via scraping.

**Acesso**: http://localhost:9095

---

### 4. Grafana (Container)

**Porta**: `3000`

**Função**: Dashboards e visualização de métricas.

**Acesso**: http://localhost:3000

**Credenciais padrão**: admin / admin

---

## Diagrama de Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                        APLICAÇÃO                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   FastAPI   │  │   Workers   │  │   Workers               │  │
│  │    (API)    │  │  (Router)   │  │  (OCR/Digital)          │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
│         │                │                     │                │
│         └────────────────┼─────────────────────┘                │
│                          │                                      │
│              ┌───────────▼───────────┐                          │
│              │   OpenTelemetry SDK   │                          │
│              │   (já integrado)      │                          │
│              └───────────┬───────────┘                          │
└──────────────────────────┼──────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │   Jaeger    │ │ Prometheus  │ │   Grafana   │
    │   :16686    │ │   :9095     │ │   :3000     │
    │  (traces)   │ │  (metrics)  │ │ (dashboards)│
    └─────────────┘ └─────────────┘ └─────────────┘
```

---

## Configuração

### Variável de Ambiente

```bash
OTEL_EXPORTER_ENDPOINT=http://jaeger:4317
```

Esta variável configura o endpoint para onde os traces são enviados.

---

## Como Subir o Ambiente

```bash
# Subir todos os serviços (inclui observabilidade)
docker compose up -d

# Verificar se estão rodando
docker compose ps
```

### Serviços de Observabilidade no docker-compose.yml:

| Serviço | Imagem | Porta |
|---------|--------|-------|
| jaeger | jaegertracing/all-in-one:1.52 | 16686, 4317-4318 |
| prometheus | prom/prometheus:v2.48.0 | 9095 |
| grafana | grafana/grafana:10.2.0 | 3000 |
| pushgateway | prom/pushgateway:v1.6.2 | 9091 |

---

## Acessos

| Ferramenta | URL | Descrição |
|------------|-----|-----------|
| **Jaeger UI** | http://localhost:16686 | Visualização de traces |
| **Prometheus** | http://localhost:9095 | Métricas e queries |
| **Grafana** | http://localhost:3000 | Dashboards |
| **Pushgateway** | http://localhost:9091 | Métricas dos workers |

---

## FAQ

### Preciso instalar o OpenTelemetry Collector?

**Não.** O OpenTelemetry SDK está integrado diretamente na aplicação Python e exporta traces diretamente para o Jaeger via protocolo OTLP.

### Preciso instalar algo além do Docker?

**Não.** Todos os componentes de observabilidade rodam como containers Docker definidos no `docker-compose.yml`.

### Como ver os traces de uma requisição?

1. Acesse http://localhost:16686 (Jaeger)
2. Selecione o serviço "irpf-processor"
3. Clique em "Find Traces"
4. Selecione um trace para ver os spans

### Como ver as métricas?

1. Acesse http://localhost:3000 (Grafana)
2. Use as credenciais: admin / admin
3. Navegue pelos dashboards pré-configurados

---

## Resumo

| Componente | Onde está? | Precisa instalar? |
|------------|------------|-------------------|
| OpenTelemetry SDK | Aplicação Python | ❌ Já incluído |
| Jaeger | Container Docker | ✅ Sobe com docker-compose |
| Prometheus | Container Docker | ✅ Sobe com docker-compose |
| Grafana | Container Docker | ✅ Sobe com docker-compose |

**Basta rodar `docker compose up -d` e tudo estará funcionando!**

---

*Documento gerado em: Janeiro 2026*
*Projeto: ASA IRPF Processor*
