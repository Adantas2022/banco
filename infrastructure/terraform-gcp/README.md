# IRPF Processor - Terraform Infrastructure (GCP)

Terraform configuration for deploying IRPF Processor to Google Cloud Platform.

## Indice

- [Arquitetura](#arquitetura)
- [Guia Rapido para Desenvolvedores](#guia-rapido-para-desenvolvedores)
- [Pre-requisitos Detalhados](#pre-requisitos-detalhados)
- [Passo a Passo Completo](#passo-a-passo-completo)
- [Ambientes](#ambientes)
- [Comandos Uteis](#comandos-uteis)
- [Troubleshooting](#troubleshooting)
- [Custos](#custos)

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GCP Project                                        │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        VPC Network                                      │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐ │ │
│  │  │  Cloud Run   │  │  Serverless  │  │     Private Services         │ │ │
│  │  │   Subnet     │  │ VPC Connector│  │  (MongoDB Atlas Peering)     │ │ │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      Cloud Run Services                               │   │
│  │  ┌─────────┐  ┌───────────────┐  ┌───────────────┐  ┌─────────────┐  │   │
│  │  │   API   │  │ Worker Router │  │Worker Digital │  │ Worker OCR  │  │   │
│  │  │ (public)│  │  (internal)   │  │  (internal)   │  │ (internal)  │  │   │
│  │  └─────────┘  └───────────────┘  └───────────────┘  └─────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────────────────┐ │
│  │  MongoDB   │  │ Memorystore│  │   Cloud    │  │  Artifact Registry    │ │
│  │   Atlas    │  │   Redis    │  │  Storage   │  │                       │ │
│  │ (external) │  │            │  │            │  │                       │ │
│  └────────────┘  └────────────┘  └────────────┘  └────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │         Cloud Monitoring  +  Cloud Logging  +  Cloud Trace              ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────────┘
```

### Componentes

| Componente | Servico GCP | Funcao |
|------------|-------------|--------|
| Database | MongoDB Atlas (via VPC Peering) | Armazenamento de documentos |
| Cache/Fila | Memorystore for Redis | Filas Dramatiq |
| Object Storage | Cloud Storage | Arquivos PDF |
| Containers | Cloud Run | API + Workers |
| Registry | Artifact Registry | Imagens Docker |
| Monitoramento | Cloud Monitoring + Logging | Logs, metricas, traces |
| Rede | VPC + VPC Access Connector | Conectividade segura |

---

## Guia Rapido para Desenvolvedores

### TL;DR - Deploy em 5 minutos

```bash
cd infrastructure/terraform-gcp

./scripts/bootstrap.sh MEU_PROJECT_ID

export TF_VAR_project_id="MEU_PROJECT_ID"
export TF_VAR_mongodb_atlas_public_key="ATLAS_PUBLIC_KEY"
export TF_VAR_mongodb_atlas_private_key="ATLAS_PRIVATE_KEY"
export TF_VAR_mongodb_atlas_org_id="ATLAS_ORG_ID"

./scripts/deploy.sh dev

./scripts/push-images.sh dev latest

echo "API URL: $(cd environments/dev && terraform output -raw api_url)"
```

---

## Pre-requisitos Detalhados

### 1. Google Cloud SDK

**macOS:**
```bash
brew install --cask google-cloud-sdk
```

**Ubuntu/Debian:**
```bash
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -
sudo apt-get update && sudo apt-get install google-cloud-cli
```

**Verificar instalacao:**
```bash
gcloud --version
```

### 2. Terraform

**macOS:**
```bash
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
```

**Ubuntu/Debian:**
```bash
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform
```

**Verificar instalacao:**
```bash
terraform --version
```

### 3. Docker

Necessario para build das imagens.

```bash
docker --version
```

### 4. Conta MongoDB Atlas

Acesse https://cloud.mongodb.com e crie uma conta (gratuita para dev).

---

## Passo a Passo Completo

### Passo 1: Autenticar no GCP

```bash
gcloud auth login

gcloud auth application-default login
```

Isso abre o navegador para autenticacao.

### Passo 2: Criar ou Selecionar Projeto GCP

**Criar novo projeto:**
```bash
gcloud projects create irpf-processor-dev --name="IRPF Processor Dev"
```

**Ou selecionar existente:**
```bash
gcloud projects list

gcloud config set project SEU_PROJECT_ID
```

### Passo 3: Habilitar Billing

Acesse https://console.cloud.google.com/billing e vincule uma conta de faturamento ao projeto.

### Passo 4: Criar Bucket para Terraform State

```bash
cd infrastructure/terraform-gcp/scripts
./bootstrap.sh SEU_PROJECT_ID
```

Esse script:
- Habilita APIs necessarias
- Cria bucket GCS para armazenar o state do Terraform
- Configura versionamento para recovery

### Passo 5: Configurar MongoDB Atlas

#### 5.1 Criar conta/login

Acesse https://cloud.mongodb.com

#### 5.2 Criar Organization (se nao tiver)

1. Clique no menu do canto superior esquerdo
2. "Create New Organization"
3. Anote o **Organization ID** (aparece na URL)

#### 5.3 Criar API Key

1. Organization Settings (engrenagem no canto superior direito)
2. Access Manager > API Keys
3. "Create API Key"
4. Nome: "Terraform IRPF Processor"
5. Permissions: **Organization Project Creator**
6. Clique "Next"
7. **IMPORTANTE:** Copie a Private Key (so aparece uma vez!)
8. Anote:
   - **Public Key:** algo como `abcdefgh`
   - **Private Key:** algo como `12345678-1234-1234-1234-123456789abc`

#### 5.4 Pegar Organization ID

1. Va para Organization Settings
2. O ID aparece no campo "Organization ID" ou na URL

### Passo 6: Exportar Credenciais

Crie um arquivo `.env.terraform` (nao commitar!):

```bash
cat > .env.terraform << 'EOF'
export TF_VAR_project_id="seu-project-id-gcp"
export TF_VAR_mongodb_atlas_public_key="sua-public-key"
export TF_VAR_mongodb_atlas_private_key="sua-private-key"
export TF_VAR_mongodb_atlas_org_id="seu-org-id"
EOF
```

Carregue as variaveis:
```bash
source .env.terraform
```

### Passo 7: Deploy da Infraestrutura

**Opcao A - Usando script:**
```bash
./scripts/deploy.sh dev
```

**Opcao B - Manualmente:**
```bash
cd environments/dev

terraform init -backend-config=backend.tfvars

terraform plan

terraform apply
```

O deploy leva aproximadamente **10-15 minutos** (MongoDB Atlas e Redis demoram).

### Passo 8: Build e Push das Imagens Docker

```bash
./scripts/push-images.sh dev latest
```

Esse script:
1. Configura Docker para autenticar no Artifact Registry
2. Builda 3 imagens:
   - `irpf-processor-api`
   - `irpf-processor-worker`
   - `irpf-processor-worker-ocr`
3. Faz push para o Artifact Registry

### Passo 9: Verificar Deploy

```bash
cd environments/dev

API_URL=$(terraform output -raw api_url)
echo "API URL: $API_URL"

curl $API_URL/health
```

Resposta esperada:
```json
{"status": "healthy"}
```

### Passo 10: Criar API Key da Aplicacao

Conecte no Cloud Run e execute:

```bash
gcloud run jobs execute create-api-key \
  --region southamerica-east1 \
  --args="--tenant-id,meu-tenant,--name,Admin Key,--admin"
```

Ou acesse o container diretamente pelo console GCP.

---

## Ambientes

| Ambiente | Uso | Auto-scaling | Custo |
|----------|-----|--------------|-------|
| **dev** | Desenvolvimento | 0-3 instancias | ~USD 100-200/mes |
| **staging** | Homologacao | 1-5 instancias | ~USD 400-600/mes |
| **prod** | Producao | 2-10 instancias | ~USD 1.000-2.000/mes |

### Trocar de Ambiente

```bash
./scripts/deploy.sh staging

./scripts/deploy.sh prod
```

### Recursos por Ambiente

| Recurso | Dev | Staging | Prod |
|---------|-----|---------|------|
| API CPU | 1 vCPU | 2 vCPU | 2 vCPU |
| API Memory | 512Mi | 1Gi | 2Gi |
| API Min Instances | 0 | 1 | 2 |
| API Max Instances | 3 | 5 | 10 |
| Worker CPU | 1 vCPU | 2 vCPU | 4 vCPU |
| Worker Memory | 1Gi | 2Gi | 4Gi |
| MongoDB Tier | M10 | M20 | M30 |
| Redis | 1GB Basic | 2GB HA | 5GB HA |

---

## Comandos Uteis

### Ver logs da API

```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=cloudrun-api-irpf-processor-dev" --limit 100
```

### Ver logs em tempo real

```bash
gcloud beta run services logs tail cloudrun-api-irpf-processor-dev --region southamerica-east1
```

### Listar servicos Cloud Run

```bash
gcloud run services list --region southamerica-east1
```

### Ver detalhes de um servico

```bash
gcloud run services describe cloudrun-api-irpf-processor-dev --region southamerica-east1
```

### Forcar novo deploy (sem mudar imagem)

```bash
gcloud run services update cloudrun-api-irpf-processor-dev \
  --region southamerica-east1 \
  --no-traffic
```

### Ver metricas do Redis

```bash
gcloud redis instances describe redis-irpf-processor-dev --region southamerica-east1
```

### Destruir ambiente

```bash
./scripts/destroy.sh dev
```

---

## Troubleshooting

### Erro: "Permission denied" no Terraform

```bash
gcloud auth application-default login
```

### Erro: "API not enabled"

```bash
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable redis.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable vpcaccess.googleapis.com
```

### Cloud Run nao inicia

```bash
gcloud logging read "resource.type=cloud_run_revision" --limit 50 --format="table(timestamp,severity,textPayload)"
```

### Erro de conexao com MongoDB Atlas

1. Verifique se o peering foi criado:
```bash
gcloud compute networks peerings list --network=vpc-irpf-processor-dev
```

2. No MongoDB Atlas, verifique:
   - Network Access > IP Access List deve ter `10.0.0.0/8`
   - Network Access > Peering deve mostrar status "Available"

### Erro de conexao com Redis

```bash
gcloud compute networks vpc-access connectors describe vpc-con-irpf-processor-dev \
  --region southamerica-east1
```

### Imagem nao encontrada no Artifact Registry

```bash
gcloud artifacts docker images list \
  southamerica-east1-docker.pkg.dev/SEU_PROJECT/repo-irpf-processor-dev
```

### Resetar state do Terraform

**CUIDADO:** Isso pode causar inconsistencias!
```bash
terraform state list

terraform state rm RECURSO_COM_PROBLEMA

terraform import RECURSO RESOURCE_ID
```

---

## Custos

### Estimativa Mensal (Sao Paulo - southamerica-east1)

| Servico | Dev | Staging | Prod |
|---------|-----|---------|------|
| Cloud Run (API) | ~USD 20 | ~USD 50 | ~USD 150 |
| Cloud Run (Workers) | ~USD 30 | ~USD 100 | ~USD 300 |
| Memorystore Redis | ~USD 35 | ~USD 100 | ~USD 250 |
| Cloud Storage | ~USD 5 | ~USD 10 | ~USD 50 |
| VPC Connector | ~USD 10 | ~USD 20 | ~USD 50 |
| Networking | ~USD 5 | ~USD 20 | ~USD 100 |
| **Subtotal GCP** | **~USD 105** | **~USD 300** | **~USD 900** |
| MongoDB Atlas | ~USD 60 | ~USD 150 | ~USD 500 |
| **TOTAL** | **~USD 165** | **~USD 450** | **~USD 1.400** |

### Dicas para Reduzir Custos em Dev

1. **Scale to zero:** API com `min_instances = 0` (ja configurado)
2. **Pausar workers:** Escale OCR worker para 0 quando nao usar
3. **MongoDB M0:** Use tier gratuito para dev (sem HA)

```bash
gcloud run services update cloudrun-worker-ocr-irpf-processor-dev \
  --region southamerica-east1 \
  --min-instances 0 \
  --max-instances 0
```

---

## Estrutura de Arquivos

```
infrastructure/terraform-gcp/
├── main.tf                    # Modulo raiz - orquestra todos os modulos
├── variables.tf               # Variaveis de entrada
├── outputs.tf                 # Outputs (URLs, connection strings)
├── versions.tf                # Versoes dos providers
├── backend.tf                 # Configuracao do state remoto
├── .gitignore                 # Ignora arquivos sensiveis
│
├── modules/
│   ├── networking/            # VPC, subnets, firewall, NAT
│   ├── database/              # MongoDB Atlas cluster + peering
│   ├── cache/                 # Memorystore Redis
│   ├── storage/               # Cloud Storage buckets
│   ├── cloudrun/              # Cloud Run services + Artifact Registry
│   └── observability/         # Monitoring dashboards + alerts
│
├── environments/
│   ├── dev/                   # Configuracao DEV
│   │   ├── main.tf
│   │   └── backend.tfvars
│   ├── staging/               # Configuracao STAGING
│   └── prod/                  # Configuracao PROD
│
└── scripts/
    ├── bootstrap.sh           # Cria bucket para state
    ├── deploy.sh              # Deploy interativo
    ├── destroy.sh             # Destroi ambiente
    └── push-images.sh         # Build e push das imagens
```

---

## Comparacao: Azure vs GCP

| Feature | Azure | GCP |
|---------|-------|-----|
| Containers | Container Apps | Cloud Run |
| MongoDB | Cosmos DB (nativo) | MongoDB Atlas (externo) |
| Redis | Azure Cache | Memorystore |
| Storage | Blob Storage | Cloud Storage |
| Registry | ACR | Artifact Registry |
| Custo Brasil | Mais alto | Mais baixo |
| Regiao | Brazil South | Sao Paulo |
| Setup MongoDB | Mais simples | Requer Atlas |

---

## Suporte

- **Docs GCP:** https://cloud.google.com/docs
- **Docs Terraform GCP:** https://registry.terraform.io/providers/hashicorp/google/latest/docs
- **MongoDB Atlas:** https://www.mongodb.com/docs/atlas/
