module "irpf_processor" {
  source = "../../"

  project_name = "irpf-processor"
  environment  = "dev"
  location     = "brazilsouth"

  vnet_address_space = ["10.0.0.0/16"]
  subnet_prefixes = {
    container_apps    = "10.0.1.0/24"
    database          = "10.0.2.0/24"
    cache             = "10.0.3.0/24"
    private_endpoints = "10.0.4.0/24"
  }

  redis_sku      = "Basic"
  redis_family   = "C"
  redis_capacity = 0

  acr_sku     = "Basic"
  app_version = "latest"

  api_cpu          = 0.25
  api_memory       = "0.5Gi"
  api_min_replicas = 1
  api_max_replicas = 3

  worker_cpu                  = 0.5
  worker_memory               = "1Gi"
  worker_digital_min_replicas = 1
  worker_digital_max_replicas = 2
  worker_ocr_min_replicas     = 1
  worker_ocr_max_replicas     = 1

  enable_monitoring  = true
  log_retention_days = 14

  tags = {
    CostCenter = "development"
    Team       = "platform"
  }
}

output "api_url" {
  value = module.irpf_processor.api_url
}

output "acr_login_server" {
  value = module.irpf_processor.acr_login_server
}

output "resource_group_name" {
  value = module.irpf_processor.resource_group_name
}
