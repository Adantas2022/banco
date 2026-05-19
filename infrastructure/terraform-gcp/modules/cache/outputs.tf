output "redis_id" {
  description = "Redis instance ID"
  value       = google_redis_instance.main.id
}

output "redis_host" {
  description = "Redis host"
  value       = google_redis_instance.main.host
}

output "redis_port" {
  description = "Redis port"
  value       = google_redis_instance.main.port
}

output "redis_auth_string" {
  description = "Redis auth string"
  value       = google_redis_instance.main.auth_string
  sensitive   = true
}

output "redis_current_location_id" {
  description = "Redis current location"
  value       = google_redis_instance.main.current_location_id
}
