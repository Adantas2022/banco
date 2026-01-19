module "irpf_processor" {
  source = "../../"

  project_name = "irpf-processor"
  project_id   = var.project_id
  environment  = "dev"
  region       = "southamerica-east1"

  mongodb_atlas_public_key  = var.mongodb_atlas_public_key
  mongodb_atlas_private_key = var.mongodb_atlas_private_key
  mongodb_atlas_org_id      = var.mongodb_atlas_org_id
  mongodb_cluster_tier      = "M10"

  redis_tier           = "BASIC"
  redis_memory_size_gb = 1

  api_cpu           = "1"
  api_memory        = "512Mi"
  api_min_instances = 0
  api_max_instances = 3

  worker_cpu                   = "1"
  worker_memory                = "1Gi"
  worker_digital_min_instances = 1
  worker_digital_max_instances = 2
  worker_ocr_min_instances     = 0
  worker_ocr_max_instances     = 1

  enable_monitoring  = true
  log_retention_days = 14

  labels = {
    cost_center = "development"
    team        = "platform"
  }
}

variable "project_id" {
  type = string
}

variable "mongodb_atlas_public_key" {
  type      = string
  sensitive = true
}

variable "mongodb_atlas_private_key" {
  type      = string
  sensitive = true
}

variable "mongodb_atlas_org_id" {
  type = string
}

output "api_url" {
  value = module.irpf_processor.api_url
}

output "artifact_registry_url" {
  value = module.irpf_processor.artifact_registry_url
}

output "project_id" {
  value = module.irpf_processor.project_id
}
