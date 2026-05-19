output "vpc_id" {
  description = "VPC ID"
  value       = google_compute_network.main.id
}

output "vpc_name" {
  description = "VPC name"
  value       = google_compute_network.main.name
}

output "vpc_self_link" {
  description = "VPC self link"
  value       = google_compute_network.main.self_link
}

output "cloudrun_subnet_id" {
  description = "Cloud Run subnet ID"
  value       = google_compute_subnetwork.cloudrun.id
}

output "cloudrun_subnet_name" {
  description = "Cloud Run subnet name"
  value       = google_compute_subnetwork.cloudrun.name
}

output "vpc_connector_id" {
  description = "VPC Access Connector ID"
  value       = google_vpc_access_connector.main.id
}

output "vpc_connector_name" {
  description = "VPC Access Connector name"
  value       = google_vpc_access_connector.main.name
}
