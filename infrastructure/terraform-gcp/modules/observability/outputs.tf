output "dashboard_id" {
  description = "Monitoring dashboard ID"
  value       = google_monitoring_dashboard.main.id
}

output "notification_channel_id" {
  description = "Notification channel ID"
  value       = var.enable_monitoring ? google_monitoring_notification_channel.email[0].id : null
}
