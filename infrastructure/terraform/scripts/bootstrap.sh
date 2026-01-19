#!/bin/bash
set -e

RESOURCE_GROUP="rg-terraform-state"
LOCATION="brazilsouth"
STORAGE_ACCOUNT="stirpfprocessortfstate"
CONTAINER_NAME="tfstate"

echo "Creating resource group for Terraform state..."
az group create \
    --name $RESOURCE_GROUP \
    --location $LOCATION

echo "Creating storage account for Terraform state..."
az storage account create \
    --name $STORAGE_ACCOUNT \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --sku Standard_LRS \
    --encryption-services blob \
    --min-tls-version TLS1_2 \
    --allow-blob-public-access false

echo "Creating blob container for Terraform state..."
az storage container create \
    --name $CONTAINER_NAME \
    --account-name $STORAGE_ACCOUNT

echo "Enabling versioning for state recovery..."
az storage account blob-service-properties update \
    --account-name $STORAGE_ACCOUNT \
    --enable-versioning true

echo "Bootstrap complete!"
echo ""
echo "Storage Account: $STORAGE_ACCOUNT"
echo "Container: $CONTAINER_NAME"
echo ""
echo "Next steps:"
echo "  cd environments/dev"
echo "  terraform init -backend-config=backend.tfvars"
echo "  terraform plan"
echo "  terraform apply"
