# IRPF Processor - Terraform Infrastructure (Azure)

Terraform configuration for deploying IRPF Processor to Azure.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Azure Resource Group                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    Virtual Network                         │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │  │
│  │  │ Container   │  │  Database   │  │    Cache    │       │  │
│  │  │ Apps Subnet │  │   Subnet    │  │   Subnet    │       │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘       │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │           Azure Container Apps Environment                  │ │
│  │  ┌────────┐  ┌─────────────┐  ┌─────────────┐             │ │
│  │  │  API   │  │   Worker    │  │   Worker    │             │ │
│  │  │        │  │   Digital   │  │    OCR      │             │ │
│  │  └────────┘  └─────────────┘  └─────────────┘             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐ │
│  │  Cosmos DB │  │   Redis    │  │   Blob     │  │   ACR    │ │
│  │  (MongoDB) │  │   Cache    │  │  Storage   │  │          │ │
│  └────────────┘  └────────────┘  └────────────┘  └──────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              Azure Monitor / Log Analytics                  │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Components

| Component | Azure Service | Purpose |
|-----------|--------------|---------|
| Database | Cosmos DB (MongoDB API) | Document storage |
| Cache/Queue | Azure Cache for Redis | Task queues (Dramatiq) |
| Object Storage | Azure Blob Storage | PDF files |
| Container Runtime | Azure Container Apps | API + Workers |
| Container Registry | Azure Container Registry | Docker images |
| Monitoring | Azure Monitor + Log Analytics | Logs and metrics |
| Networking | VNet + Private Endpoints | Secure connectivity |

## Prerequisites

1. Azure CLI installed and configured
2. Terraform >= 1.5.0
3. Azure subscription with appropriate permissions

## Setup

### 1. Create Terraform State Storage

Run the bootstrap script to create the storage account for Terraform state:

```bash
./scripts/bootstrap.sh
```

### 2. Login to Azure

```bash
az login
az account set --subscription <SUBSCRIPTION_ID>
```

### 3. Deploy to an Environment

```bash
cd environments/dev

terraform init -backend-config=backend.tfvars
terraform plan
terraform apply
```

## Environments

| Environment | Purpose | Resources |
|-------------|---------|-----------|
| dev | Development | Minimal resources, low cost |
| staging | Pre-production | Moderate resources |
| prod | Production | Full resources, HA |

### Resource Sizing by Environment

| Resource | Dev | Staging | Prod |
|----------|-----|---------|------|
| API CPU | 0.25 cores | 0.5 cores | 1.0 cores |
| API Memory | 0.5 Gi | 1 Gi | 2 Gi |
| API Replicas | 1-3 | 2-5 | 3-10 |
| Worker CPU | 0.5 cores | 1.0 cores | 2.0 cores |
| Worker Memory | 1 Gi | 2 Gi | 4 Gi |
| Redis SKU | Basic/C0 | Standard/C1 | Premium/P1 |
| ACR SKU | Basic | Standard | Premium |

## Deploying Application

After infrastructure is provisioned:

### 1. Build and Push Images

```bash
ACR_NAME=$(terraform output -raw acr_login_server)

az acr login --name $ACR_NAME

docker build -t $ACR_NAME/irpf-processor-api:latest --target api .
docker build -t $ACR_NAME/irpf-processor-worker:latest --target worker .
docker build -t $ACR_NAME/irpf-processor-worker-ocr:latest --target worker-ocr .

docker push $ACR_NAME/irpf-processor-api:latest
docker push $ACR_NAME/irpf-processor-worker:latest
docker push $ACR_NAME/irpf-processor-worker-ocr:latest
```

### 2. Update Container Apps

Container Apps will automatically pull new images on restart or you can force an update:

```bash
az containerapp update \
  --name ca-api-irpf-processor-dev \
  --resource-group rg-irpf-processor-dev
```

## Module Structure

```
infrastructure/terraform/
├── main.tf              # Root module
├── variables.tf         # Input variables
├── outputs.tf           # Output values
├── versions.tf          # Provider versions
├── backend.tf           # Remote state config
├── modules/
│   ├── networking/      # VNet, subnets, NSGs
│   ├── database/        # Cosmos DB
│   ├── cache/           # Redis
│   ├── storage/         # Blob Storage
│   ├── containers/      # Container Apps + ACR
│   └── observability/   # Log Analytics + Alerts
└── environments/
    ├── dev/             # Development config
    ├── staging/         # Staging config
    └── prod/            # Production config
```

## Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| project_name | Project name | irpf-processor |
| environment | Environment (dev/staging/prod) | - |
| location | Azure region | brazilsouth |
| api_min_replicas | Min API replicas | 1 |
| api_max_replicas | Max API replicas | 5 |
| enable_monitoring | Enable alerts | true |

See `variables.tf` for complete list.

## Outputs

| Output | Description |
|--------|-------------|
| api_url | Public API URL |
| acr_login_server | ACR server for docker push |
| resource_group_name | Resource group name |
| cosmosdb_connection_string | MongoDB connection string (sensitive) |
| redis_connection_string | Redis URL (sensitive) |

## Cost Estimation (Brazil South)

| Environment | Estimated Monthly Cost |
|-------------|----------------------|
| Dev | ~R$ 500-800 |
| Staging | ~R$ 1.500-2.500 |
| Prod | ~R$ 4.000-8.000 |

Costs vary based on usage and data transfer.

## Security

- All services use private endpoints
- Public network access disabled
- TLS 1.2 minimum
- Secrets stored in Container Apps secrets
- Network isolation via VNet
