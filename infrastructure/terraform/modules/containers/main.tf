resource "azurerm_container_registry" "main" {
  name                = "acr${replace(var.resource_prefix, "-", "")}"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = var.acr_sku
  admin_enabled       = true

  tags = var.tags
}

resource "azurerm_container_app_environment" "main" {
  name                       = "cae-${var.resource_prefix}"
  resource_group_name        = var.resource_group_name
  location                   = var.location
  log_analytics_workspace_id = var.log_analytics_workspace_id
  infrastructure_subnet_id   = var.subnet_id

  tags = var.tags
}

resource "azurerm_container_app" "api" {
  name                         = "ca-api-${var.resource_prefix}"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"

  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password"
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }

  secret {
    name  = "mongo-uri"
    value = var.cosmosdb_connection_string
  }

  secret {
    name  = "redis-url"
    value = var.redis_connection_string
  }

  secret {
    name  = "storage-connection"
    value = var.storage_connection_string
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  template {
    min_replicas = var.api_min_replicas
    max_replicas = var.api_max_replicas

    container {
      name   = "api"
      image  = "${azurerm_container_registry.main.login_server}/irpf-processor-api:${var.app_version}"
      cpu    = var.api_cpu
      memory = var.api_memory

      env {
        name  = "APP_ENV"
        value = var.environment
      }

      env {
        name        = "MONGO_URI"
        secret_name = "mongo-uri"
      }

      env {
        name        = "REDIS_URL"
        secret_name = "redis-url"
      }

      env {
        name        = "AZURE_STORAGE_CONNECTION_STRING"
        secret_name = "storage-connection"
      }

      env {
        name  = "STORAGE_CONTAINER"
        value = var.storage_container_name
      }

      env {
        name  = "LOG_LEVEL"
        value = var.environment == "prod" ? "INFO" : "DEBUG"
      }

      liveness_probe {
        path             = "/health"
        port             = 8000
        transport        = "HTTP"
        initial_delay    = 30
        interval_seconds = 30
      }

      readiness_probe {
        path             = "/health"
        port             = 8000
        transport        = "HTTP"
        initial_delay    = 10
        interval_seconds = 10
      }
    }

    http_scale_rule {
      name                = "http-scaling"
      concurrent_requests = "100"
    }
  }

  tags = var.tags
}

resource "azurerm_container_app" "worker_router" {
  name                         = "ca-worker-router-${var.resource_prefix}"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"

  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password"
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }

  secret {
    name  = "mongo-uri"
    value = var.cosmosdb_connection_string
  }

  secret {
    name  = "redis-url"
    value = var.redis_connection_string
  }

  secret {
    name  = "storage-connection"
    value = var.storage_connection_string
  }

  template {
    min_replicas = 1
    max_replicas = 1

    container {
      name   = "worker-router"
      image  = "${azurerm_container_registry.main.login_server}/irpf-processor-worker:${var.app_version}"
      cpu    = var.worker_cpu
      memory = var.worker_memory

      command = [
        "dramatiq",
        "irpf_processor.presentation.workers",
        "--queues", "extraction-router",
        "--processes", "1",
        "--threads", "2"
      ]

      env {
        name  = "APP_ENV"
        value = var.environment
      }

      env {
        name        = "MONGO_URI"
        secret_name = "mongo-uri"
      }

      env {
        name        = "REDIS_URL"
        secret_name = "redis-url"
      }

      env {
        name        = "AZURE_STORAGE_CONNECTION_STRING"
        secret_name = "storage-connection"
      }

      env {
        name  = "STORAGE_CONTAINER"
        value = var.storage_container_name
      }
    }
  }

  tags = var.tags
}

resource "azurerm_container_app" "worker_digital" {
  name                         = "ca-worker-digital-${var.resource_prefix}"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"

  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password"
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }

  secret {
    name  = "mongo-uri"
    value = var.cosmosdb_connection_string
  }

  secret {
    name  = "redis-url"
    value = var.redis_connection_string
  }

  secret {
    name  = "storage-connection"
    value = var.storage_connection_string
  }

  template {
    min_replicas = var.worker_digital_min_replicas
    max_replicas = var.worker_digital_max_replicas

    container {
      name   = "worker-digital"
      image  = "${azurerm_container_registry.main.login_server}/irpf-processor-worker:${var.app_version}"
      cpu    = var.worker_cpu
      memory = var.worker_memory

      command = [
        "dramatiq",
        "irpf_processor.presentation.workers",
        "--queues", "default",
        "--processes", "2",
        "--threads", "4"
      ]

      env {
        name  = "APP_ENV"
        value = var.environment
      }

      env {
        name        = "MONGO_URI"
        secret_name = "mongo-uri"
      }

      env {
        name        = "REDIS_URL"
        secret_name = "redis-url"
      }

      env {
        name        = "AZURE_STORAGE_CONNECTION_STRING"
        secret_name = "storage-connection"
      }

      env {
        name  = "STORAGE_CONTAINER"
        value = var.storage_container_name
      }
    }
  }

  tags = var.tags
}

resource "azurerm_container_app" "worker_ocr" {
  name                         = "ca-worker-ocr-${var.resource_prefix}"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"

  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password"
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }

  secret {
    name  = "mongo-uri"
    value = var.cosmosdb_connection_string
  }

  secret {
    name  = "redis-url"
    value = var.redis_connection_string
  }

  secret {
    name  = "storage-connection"
    value = var.storage_connection_string
  }

  template {
    min_replicas = var.worker_ocr_min_replicas
    max_replicas = var.worker_ocr_max_replicas

    container {
      name   = "worker-ocr"
      image  = "${azurerm_container_registry.main.login_server}/irpf-processor-worker-ocr:${var.app_version}"
      cpu    = var.worker_cpu
      memory = var.worker_memory

      command = [
        "dramatiq",
        "irpf_processor.presentation.workers.ocr_worker",
        "--queues", "extraction-ocr",
        "--processes", "1",
        "--threads", "1"
      ]

      env {
        name  = "APP_ENV"
        value = var.environment
      }

      env {
        name        = "MONGO_URI"
        secret_name = "mongo-uri"
      }

      env {
        name        = "REDIS_URL"
        secret_name = "redis-url"
      }

      env {
        name        = "AZURE_STORAGE_CONNECTION_STRING"
        secret_name = "storage-connection"
      }

      env {
        name  = "STORAGE_CONTAINER"
        value = var.storage_container_name
      }

      env {
        name  = "OCR_ENGINE"
        value = "docling"
      }

      env {
        name  = "OCR_TIMEOUT_SECONDS"
        value = "300"
      }
    }
  }

  tags = var.tags
}
