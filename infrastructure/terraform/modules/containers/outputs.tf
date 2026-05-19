output "acr_id" {
  description = "ACR ID"
  value       = azurerm_container_registry.main.id
}

output "acr_login_server" {
  description = "ACR login server"
  value       = azurerm_container_registry.main.login_server
}

output "acr_admin_username" {
  description = "ACR admin username"
  value       = azurerm_container_registry.main.admin_username
}

output "acr_admin_password" {
  description = "ACR admin password"
  value       = azurerm_container_registry.main.admin_password
  sensitive   = true
}

output "environment_id" {
  description = "Container Apps Environment ID"
  value       = azurerm_container_app_environment.main.id
}

output "environment_name" {
  description = "Container Apps Environment name"
  value       = azurerm_container_app_environment.main.name
}

output "api_url" {
  description = "API URL"
  value       = "https://${azurerm_container_app.api.ingress[0].fqdn}"
}

output "api_fqdn" {
  description = "API FQDN"
  value       = azurerm_container_app.api.ingress[0].fqdn
}

output "ecr_repository_url" {
  description = "ECR repository URL (alias for ACR)"
  value       = azurerm_container_registry.main.login_server
}
