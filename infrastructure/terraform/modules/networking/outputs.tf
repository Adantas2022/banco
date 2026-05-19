output "vnet_id" {
  description = "Virtual Network ID"
  value       = azurerm_virtual_network.main.id
}

output "vnet_name" {
  description = "Virtual Network name"
  value       = azurerm_virtual_network.main.name
}

output "container_apps_subnet_id" {
  description = "Container Apps subnet ID"
  value       = azurerm_subnet.container_apps.id
}

output "database_subnet_id" {
  description = "Database subnet ID"
  value       = azurerm_subnet.database.id
}

output "cache_subnet_id" {
  description = "Cache subnet ID"
  value       = azurerm_subnet.cache.id
}

output "private_endpoints_subnet_id" {
  description = "Private endpoints subnet ID"
  value       = azurerm_subnet.private_endpoints.id
}

output "blob_private_dns_zone_id" {
  description = "Blob private DNS zone ID"
  value       = azurerm_private_dns_zone.blob.id
}

output "cosmosdb_private_dns_zone_id" {
  description = "Cosmos DB private DNS zone ID"
  value       = azurerm_private_dns_zone.cosmosdb.id
}

output "redis_private_dns_zone_id" {
  description = "Redis private DNS zone ID"
  value       = azurerm_private_dns_zone.redis.id
}
