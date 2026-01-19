locals {
  resource_prefix = "${var.project_name}-${var.environment}"
  
  common_tags = merge(var.tags, {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  })
}

resource "azurerm_resource_group" "main" {
  name     = "rg-${local.resource_prefix}"
  location = var.location
  tags     = local.common_tags
}

module "networking" {
  source = "./modules/networking"

  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  resource_prefix     = local.resource_prefix
  vnet_address_space  = var.vnet_address_space
  subnet_prefixes     = var.subnet_prefixes
  tags                = local.common_tags
}

module "observability" {
  source = "./modules/observability"

  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  resource_prefix     = local.resource_prefix
  retention_days      = var.log_retention_days
  enable_monitoring   = var.enable_monitoring
  tags                = local.common_tags
}

module "storage" {
  source = "./modules/storage"

  resource_group_name   = azurerm_resource_group.main.name
  location              = var.location
  resource_prefix       = local.resource_prefix
  subnet_id             = module.networking.private_endpoints_subnet_id
  private_dns_zone_id   = module.networking.blob_private_dns_zone_id
  tags                  = local.common_tags
}

module "database" {
  source = "./modules/database"

  resource_group_name     = azurerm_resource_group.main.name
  location                = var.location
  resource_prefix         = local.resource_prefix
  subnet_id               = module.networking.database_subnet_id
  private_dns_zone_id     = module.networking.cosmosdb_private_dns_zone_id
  throughput              = var.cosmosdb_throughput
  max_throughput          = var.cosmosdb_max_throughput
  tags                    = local.common_tags
}

module "cache" {
  source = "./modules/cache"

  resource_group_name   = azurerm_resource_group.main.name
  location              = var.location
  resource_prefix       = local.resource_prefix
  subnet_id             = module.networking.cache_subnet_id
  private_dns_zone_id   = module.networking.redis_private_dns_zone_id
  sku                   = var.redis_sku
  family                = var.redis_family
  capacity              = var.redis_capacity
  tags                  = local.common_tags
}

module "containers" {
  source = "./modules/containers"

  resource_group_name         = azurerm_resource_group.main.name
  location                    = var.location
  resource_prefix             = local.resource_prefix
  environment                 = var.environment
  
  subnet_id                   = module.networking.container_apps_subnet_id
  log_analytics_workspace_id  = module.observability.workspace_id
  
  acr_sku                     = var.acr_sku
  app_version                 = var.app_version
  
  cosmosdb_connection_string  = module.database.connection_string
  redis_connection_string     = module.cache.connection_string
  storage_connection_string   = module.storage.connection_string
  storage_container_name      = module.storage.container_name
  
  api_cpu                     = var.api_cpu
  api_memory                  = var.api_memory
  api_min_replicas            = var.api_min_replicas
  api_max_replicas            = var.api_max_replicas
  
  worker_cpu                  = var.worker_cpu
  worker_memory               = var.worker_memory
  worker_digital_min_replicas = var.worker_digital_min_replicas
  worker_digital_max_replicas = var.worker_digital_max_replicas
  worker_ocr_min_replicas     = var.worker_ocr_min_replicas
  worker_ocr_max_replicas     = var.worker_ocr_max_replicas
  
  tags                        = local.common_tags
}
