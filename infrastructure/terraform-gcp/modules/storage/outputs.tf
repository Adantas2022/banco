output "bucket_name" {
  description = "Documents bucket name"
  value       = google_storage_bucket.documents.name
}

output "bucket_url" {
  description = "Documents bucket URL"
  value       = google_storage_bucket.documents.url
}

output "bucket_self_link" {
  description = "Documents bucket self link"
  value       = google_storage_bucket.documents.self_link
}

output "processed_bucket_name" {
  description = "Processed bucket name"
  value       = google_storage_bucket.processed.name
}
