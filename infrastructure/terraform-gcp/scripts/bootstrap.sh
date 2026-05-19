#!/bin/bash
set -e

PROJECT_ID=${1:-}
REGION=${2:-southamerica-east1}
BUCKET_NAME="tfstate-irpf-processor"

if [ -z "$PROJECT_ID" ]; then
    echo "Usage: $0 <project-id> [region]"
    echo "  project-id: GCP project ID"
    echo "  region: GCP region (default: southamerica-east1)"
    exit 1
fi

echo "Setting project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

echo "Enabling required APIs..."
gcloud services enable \
    storage.googleapis.com \
    cloudresourcemanager.googleapis.com

echo "Creating GCS bucket for Terraform state..."
gsutil mb -p $PROJECT_ID -l $REGION -b on gs://$BUCKET_NAME || echo "Bucket already exists"

echo "Enabling versioning..."
gsutil versioning set on gs://$BUCKET_NAME

echo "Setting uniform bucket-level access..."
gsutil uniformbucketlevelaccess set on gs://$BUCKET_NAME

echo "Bootstrap complete!"
echo ""
echo "Bucket: gs://$BUCKET_NAME"
echo ""
echo "Next steps:"
echo "  1. Create MongoDB Atlas API keys at https://cloud.mongodb.com"
echo "  2. Export credentials:"
echo "     export TF_VAR_project_id=$PROJECT_ID"
echo "     export TF_VAR_mongodb_atlas_public_key=xxx"
echo "     export TF_VAR_mongodb_atlas_private_key=xxx"
echo "     export TF_VAR_mongodb_atlas_org_id=xxx"
echo "  3. Deploy:"
echo "     cd environments/dev"
echo "     terraform init -backend-config=backend.tfvars"
echo "     terraform plan"
echo "     terraform apply"
