output "project_id" {
  description = "GCP Project ID"
  value       = var.project_id
}

output "region" {
  description = "GCP Region"
  value       = var.region
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.networking.vpc_id
}

output "vpc_name" {
  description = "VPC name"
  value       = module.networking.vpc_name
}

output "mongodb_connection_string" {
  description = "MongoDB Atlas connection string"
  value       = module.database.connection_string
  sensitive   = true
}

output "redis_host" {
  description = "Redis host"
  value       = module.cache.redis_host
}

output "redis_connection_string" {
  description = "Redis connection string"
  value       = "redis://${module.cache.redis_host}:${module.cache.redis_port}/0"
  sensitive   = true
}

output "storage_bucket_name" {
  description = "Cloud Storage bucket name"
  value       = module.storage.bucket_name
}

output "storage_bucket_url" {
  description = "Cloud Storage bucket URL"
  value       = module.storage.bucket_url
}

output "artifact_registry_url" {
  description = "Artifact Registry URL"
  value       = module.cloudrun.artifact_registry_url
}

output "api_url" {
  description = "API URL"
  value       = module.cloudrun.api_url
}

output "api_service_name" {
  description = "API Cloud Run service name"
  value       = module.cloudrun.api_service_name
}

output "worker_router_service_name" {
  description = "Worker Router service name"
  value       = module.cloudrun.worker_router_service_name
}

output "worker_digital_service_name" {
  description = "Worker Digital service name"
  value       = module.cloudrun.worker_digital_service_name
}

output "worker_ocr_service_name" {
  description = "Worker OCR service name"
  value       = module.cloudrun.worker_ocr_service_name
}
