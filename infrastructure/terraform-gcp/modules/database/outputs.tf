output "cluster_id" {
  description = "MongoDB Atlas cluster ID"
  value       = mongodbatlas_cluster.main.cluster_id
}

output "cluster_name" {
  description = "MongoDB Atlas cluster name"
  value       = mongodbatlas_cluster.main.name
}

output "connection_string" {
  description = "MongoDB connection string"
  value       = "mongodb+srv://${mongodbatlas_database_user.main.username}:${random_password.mongodb.result}@${replace(mongodbatlas_cluster.main.connection_strings[0].standard_srv, "mongodb+srv://", "")}/irpf_processor?retryWrites=true&w=majority"
  sensitive   = true
}

output "connection_string_private" {
  description = "MongoDB private connection string"
  value       = mongodbatlas_cluster.main.connection_strings[0].private_srv
  sensitive   = true
}

output "project_id" {
  description = "MongoDB Atlas project ID"
  value       = mongodbatlas_project.main.id
}
