module "irpf_processor" {
  source = "../../"

  project_name = "irpf-processor"
  environment  = "staging"
  location     = "brazilsouth"

  vnet_address_space = ["10.1.0.0/16"]
  subnet_prefixes = {
    container_apps    = "10.1.1.0/24"
    database          = "10.1.2.0/24"
    cache             = "10.1.3.0/24"
    private_endpoints = "10.1.4.0/24"
  }

  redis_sku      = "Standard"
  redis_family   = "C"
  redis_capacity = 1

  acr_sku     = "Standard"
  app_version = "latest"

  api_cpu          = 0.5
  api_memory       = "1Gi"
  api_min_replicas = 2
  api_max_replicas = 5

  worker_cpu                  = 1.0
  worker_memory               = "2Gi"
  worker_digital_min_replicas = 2
  worker_digital_max_replicas = 4
  worker_ocr_min_replicas     = 1
  worker_ocr_max_replicas     = 2

  enable_monitoring  = true
  log_retention_days = 30

  tags = {
    CostCenter = "staging"
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
