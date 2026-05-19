resource "google_artifact_registry_repository" "main" {
  project       = var.project_id
  location      = var.region
  repository_id = "repo-${var.resource_prefix}"
  format        = "DOCKER"
  description   = "Docker repository for IRPF Processor"

  labels = var.labels
}

resource "google_service_account" "cloudrun" {
  project      = var.project_id
  account_id   = "sa-cloudrun-${var.resource_prefix}"
  display_name = "Cloud Run Service Account - ${var.resource_prefix}"
}

resource "google_project_iam_member" "cloudrun_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.cloudrun.email}"
}

resource "google_project_iam_member" "cloudrun_secretmanager" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.cloudrun.email}"
}

resource "google_project_iam_member" "cloudrun_trace" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.cloudrun.email}"
}

resource "google_secret_manager_secret" "mongodb_uri" {
  project   = var.project_id
  secret_id = "mongodb-uri-${var.resource_prefix}"

  replication {
    auto {}
  }

  labels = var.labels
}

resource "google_secret_manager_secret_version" "mongodb_uri" {
  secret      = google_secret_manager_secret.mongodb_uri.id
  secret_data = var.mongodb_connection_string
}

resource "google_secret_manager_secret" "redis_auth" {
  project   = var.project_id
  secret_id = "redis-auth-${var.resource_prefix}"

  replication {
    auto {}
  }

  labels = var.labels
}

resource "google_cloud_run_v2_service" "api" {
  name     = "cloudrun-api-${var.resource_prefix}"
  project  = var.project_id
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.cloudrun.email

    scaling {
      min_instance_count = var.api_min_instances
      max_instance_count = var.api_max_instances
    }

    vpc_access {
      connector = var.vpc_connector_id
      egress    = "ALL_TRAFFIC"
    }

    containers {
      name  = "api"
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.main.repository_id}/irpf-processor-api:${var.app_version}"

      resources {
        limits = {
          cpu    = var.api_cpu
          memory = var.api_memory
        }
      }

      ports {
        container_port = 8000
      }

      env {
        name  = "APP_ENV"
        value = var.environment
      }

      env {
        name  = "LOG_LEVEL"
        value = var.environment == "prod" ? "INFO" : "DEBUG"
      }

      env {
        name = "MONGO_URI"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.mongodb_uri.secret_id
            version = "latest"
          }
        }
      }

      env {
        name  = "REDIS_HOST"
        value = var.redis_host
      }

      env {
        name  = "REDIS_PORT"
        value = tostring(var.redis_port)
      }

      env {
        name  = "GCS_BUCKET"
        value = var.storage_bucket
      }

      env {
        name  = "OTEL_ENABLED"
        value = "true"
      }

      startup_probe {
        http_get {
          path = "/health"
          port = 8000
        }
        initial_delay_seconds = 10
        period_seconds        = 10
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/health"
          port = 8000
        }
        period_seconds    = 30
        failure_threshold = 3
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  labels = var.labels
}

resource "google_cloud_run_service_iam_member" "api_public" {
  project  = var.project_id
  location = var.region
  service  = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service" "worker_router" {
  name     = "cloudrun-worker-router-${var.resource_prefix}"
  project  = var.project_id
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.cloudrun.email

    scaling {
      min_instance_count = 1
      max_instance_count = 1
    }

    vpc_access {
      connector = var.vpc_connector_id
      egress    = "ALL_TRAFFIC"
    }

    containers {
      name  = "worker-router"
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.main.repository_id}/irpf-processor-worker:${var.app_version}"

      resources {
        limits = {
          cpu    = var.worker_cpu
          memory = var.worker_memory
        }
      }

      command = ["dramatiq", "irpf_processor.presentation.workers", "--queues", "extraction-router", "--processes", "1", "--threads", "2"]

      env {
        name  = "APP_ENV"
        value = var.environment
      }

      env {
        name = "MONGO_URI"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.mongodb_uri.secret_id
            version = "latest"
          }
        }
      }

      env {
        name  = "REDIS_HOST"
        value = var.redis_host
      }

      env {
        name  = "REDIS_PORT"
        value = tostring(var.redis_port)
      }

      env {
        name  = "GCS_BUCKET"
        value = var.storage_bucket
      }
    }
  }

  labels = var.labels
}

resource "google_cloud_run_v2_service" "worker_digital" {
  name     = "cloudrun-worker-digital-${var.resource_prefix}"
  project  = var.project_id
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.cloudrun.email

    scaling {
      min_instance_count = var.worker_digital_min_instances
      max_instance_count = var.worker_digital_max_instances
    }

    vpc_access {
      connector = var.vpc_connector_id
      egress    = "ALL_TRAFFIC"
    }

    containers {
      name  = "worker-digital"
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.main.repository_id}/irpf-processor-worker:${var.app_version}"

      resources {
        limits = {
          cpu    = var.worker_cpu
          memory = var.worker_memory
        }
      }

      command = ["dramatiq", "irpf_processor.presentation.workers", "--queues", "default", "--processes", "2", "--threads", "4"]

      env {
        name  = "APP_ENV"
        value = var.environment
      }

      env {
        name = "MONGO_URI"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.mongodb_uri.secret_id
            version = "latest"
          }
        }
      }

      env {
        name  = "REDIS_HOST"
        value = var.redis_host
      }

      env {
        name  = "REDIS_PORT"
        value = tostring(var.redis_port)
      }

      env {
        name  = "GCS_BUCKET"
        value = var.storage_bucket
      }
    }
  }

  labels = var.labels
}

resource "google_cloud_run_v2_service" "worker_ocr" {
  name     = "cloudrun-worker-ocr-${var.resource_prefix}"
  project  = var.project_id
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.cloudrun.email

    timeout = "600s"

    scaling {
      min_instance_count = var.worker_ocr_min_instances
      max_instance_count = var.worker_ocr_max_instances
    }

    vpc_access {
      connector = var.vpc_connector_id
      egress    = "ALL_TRAFFIC"
    }

    containers {
      name  = "worker-ocr"
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.main.repository_id}/irpf-processor-worker-ocr:${var.app_version}"

      resources {
        limits = {
          cpu    = var.worker_cpu
          memory = var.worker_memory
        }
      }

      command = ["dramatiq", "irpf_processor.presentation.workers.ocr_worker", "--queues", "extraction-ocr", "--processes", "1", "--threads", "1"]

      env {
        name  = "APP_ENV"
        value = var.environment
      }

      env {
        name = "MONGO_URI"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.mongodb_uri.secret_id
            version = "latest"
          }
        }
      }

      env {
        name  = "REDIS_HOST"
        value = var.redis_host
      }

      env {
        name  = "REDIS_PORT"
        value = tostring(var.redis_port)
      }

      env {
        name  = "GCS_BUCKET"
        value = var.storage_bucket
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

  labels = var.labels
}
