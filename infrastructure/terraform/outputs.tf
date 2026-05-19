output "resource_group_name" {
  description = "Resource group name"
  value       = azurerm_resource_group.main.name
}

output "vnet_id" {
  description = "Virtual Network ID"
  value       = module.networking.vnet_id
}

output "cosmosdb_connection_string" {
  description = "Cosmos DB MongoDB connection string"
  value       = module.database.connection_string
  sensitive   = true
}

output "cosmosdb_endpoint" {
  description = "Cosmos DB endpoint"
  value       = module.database.endpoint
}

output "redis_hostname" {
  description = "Redis hostname"
  value       = module.cache.hostname
}

output "redis_connection_string" {
  description = "Redis connection string"
  value       = module.cache.connection_string
  sensitive   = true
}

output "storage_account_name" {
  description = "Storage account name"
  value       = module.storage.storage_account_name
}

output "storage_container_name" {
  description = "Blob container name for documents"
  value       = module.storage.container_name
}

output "storage_connection_string" {
  description = "Storage account connection string"
  value       = module.storage.connection_string
  sensitive   = true
}

output "acr_login_server" {
  description = "ACR login server"
  value       = module.containers.acr_login_server
}

output "api_url" {
  description = "API URL"
  value       = module.containers.api_url
}

output "container_apps_environment_id" {
  description = "Container Apps Environment ID"
  value       = module.containers.environment_id
}

output "log_analytics_workspace_id" {
  description = "Log Analytics Workspace ID"
  value       = module.observability.workspace_id
}
