locals {
  resource_prefix = "${var.project_name}-${var.environment}"

  common_labels = merge(var.labels, {
    project     = var.project_name
    environment = var.environment
    managed_by  = "terraform"
  })
}

resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com",
    "vpcaccess.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "redis.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "cloudtrace.googleapis.com",
    "servicenetworking.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

module "networking" {
  source = "./modules/networking"

  project_id      = var.project_id
  region          = var.region
  resource_prefix = local.resource_prefix
  vpc_cidr        = var.vpc_cidr
  subnet_ranges   = var.subnet_ranges
  labels          = local.common_labels

  depends_on = [google_project_service.required_apis]
}

module "observability" {
  source = "./modules/observability"

  project_id        = var.project_id
  resource_prefix   = local.resource_prefix
  environment       = var.environment
  log_retention_days = var.log_retention_days
  enable_monitoring = var.enable_monitoring
  labels            = local.common_labels
}

module "storage" {
  source = "./modules/storage"

  project_id      = var.project_id
  region          = var.region
  resource_prefix = local.resource_prefix
  labels          = local.common_labels
}

module "database" {
  source = "./modules/database"

  project_id              = var.project_id
  region                  = var.region
  resource_prefix         = local.resource_prefix
  environment             = var.environment
  mongodb_atlas_org_id    = var.mongodb_atlas_org_id
  cluster_tier            = var.mongodb_cluster_tier
  vpc_network_name        = module.networking.vpc_name
  labels                  = local.common_labels
}

module "cache" {
  source = "./modules/cache"

  project_id       = var.project_id
  region           = var.region
  resource_prefix  = local.resource_prefix
  vpc_network_id   = module.networking.vpc_id
  tier             = var.redis_tier
  memory_size_gb   = var.redis_memory_size_gb
  labels           = local.common_labels

  depends_on = [google_project_service.required_apis]
}

module "cloudrun" {
  source = "./modules/cloudrun"

  project_id      = var.project_id
  region          = var.region
  resource_prefix = local.resource_prefix
  environment     = var.environment

  vpc_connector_id = module.networking.vpc_connector_id

  app_version = var.app_version

  mongodb_connection_string = module.database.connection_string
  redis_host                = module.cache.redis_host
  redis_port                = module.cache.redis_port
  storage_bucket            = module.storage.bucket_name

  api_cpu           = var.api_cpu
  api_memory        = var.api_memory
  api_min_instances = var.api_min_instances
  api_max_instances = var.api_max_instances

  worker_cpu                   = var.worker_cpu
  worker_memory                = var.worker_memory
  worker_digital_min_instances = var.worker_digital_min_instances
  worker_digital_max_instances = var.worker_digital_max_instances
  worker_ocr_min_instances     = var.worker_ocr_min_instances
  worker_ocr_max_instances     = var.worker_ocr_max_instances

  labels = local.common_labels

  depends_on = [
    google_project_service.required_apis,
    module.networking,
    module.database,
    module.cache,
    module.storage,
  ]
}
