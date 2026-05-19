output "id" {
  description = "Redis cache ID"
  value       = azurerm_redis_cache.main.id
}

output "hostname" {
  description = "Redis hostname"
  value       = azurerm_redis_cache.main.hostname
}

output "port" {
  description = "Redis SSL port"
  value       = azurerm_redis_cache.main.ssl_port
}

output "primary_access_key" {
  description = "Redis primary access key"
  value       = azurerm_redis_cache.main.primary_access_key
  sensitive   = true
}

output "connection_string" {
  description = "Redis connection string"
  value       = "rediss://:${azurerm_redis_cache.main.primary_access_key}@${azurerm_redis_cache.main.hostname}:${azurerm_redis_cache.main.ssl_port}/0"
  sensitive   = true
}
