resource "google_redis_instance" "main" {
  name           = "redis-${var.resource_prefix}"
  project        = var.project_id
  region         = var.region
  tier           = var.tier
  memory_size_gb = var.memory_size_gb

  authorized_network = var.vpc_network_id

  redis_version = "REDIS_7_0"

  display_name = "Redis ${var.resource_prefix}"

  auth_enabled            = true
  transit_encryption_mode = "SERVER_AUTHENTICATION"

  maintenance_policy {
    weekly_maintenance_window {
      day = "SUNDAY"
      start_time {
        hours   = 3
        minutes = 0
      }
    }
  }

  redis_configs = {
    maxmemory-policy = "allkeys-lru"
  }

  labels = var.labels
}
