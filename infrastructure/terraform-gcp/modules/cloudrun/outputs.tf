output "artifact_registry_url" {
  description = "Artifact Registry URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.main.repository_id}"
}

output "artifact_registry_id" {
  description = "Artifact Registry ID"
  value       = google_artifact_registry_repository.main.id
}

output "service_account_email" {
  description = "Cloud Run service account email"
  value       = google_service_account.cloudrun.email
}

output "api_url" {
  description = "API URL"
  value       = google_cloud_run_v2_service.api.uri
}

output "api_service_name" {
  description = "API service name"
  value       = google_cloud_run_v2_service.api.name
}

output "worker_router_service_name" {
  description = "Worker Router service name"
  value       = google_cloud_run_v2_service.worker_router.name
}

output "worker_digital_service_name" {
  description = "Worker Digital service name"
  value       = google_cloud_run_v2_service.worker_digital.name
}

output "worker_ocr_service_name" {
  description = "Worker OCR service name"
  value       = google_cloud_run_v2_service.worker_ocr.name
}
