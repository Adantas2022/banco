resource "google_logging_project_bucket_config" "main" {
  project        = var.project_id
  location       = "global"
  retention_days = var.log_retention_days
  bucket_id      = "_Default"
}

resource "google_monitoring_notification_channel" "email" {
  count = var.enable_monitoring ? 1 : 0

  project      = var.project_id
  display_name = "Email Alerts - ${var.resource_prefix}"
  type         = "email"

  labels = {
    email_address = "alerts@asabank.com.br"
  }
}

resource "google_monitoring_alert_policy" "api_latency" {
  count = var.enable_monitoring ? 1 : 0

  project      = var.project_id
  display_name = "API High Latency - ${var.resource_prefix}"
  combiner     = "OR"

  conditions {
    display_name = "Cloud Run request latency > 5s"

    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND metric.type = \"run.googleapis.com/request_latencies\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 5000

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_PERCENTILE_95"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email[0].name]

  alert_strategy {
    auto_close = "604800s"
  }
}

resource "google_monitoring_alert_policy" "api_errors" {
  count = var.enable_monitoring ? 1 : 0

  project      = var.project_id
  display_name = "API High Error Rate - ${var.resource_prefix}"
  combiner     = "OR"

  conditions {
    display_name = "Cloud Run error rate > 5%"

    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND metric.type = \"run.googleapis.com/request_count\" AND metric.labels.response_code_class != \"2xx\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.05

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email[0].name]

  alert_strategy {
    auto_close = "604800s"
  }
}

resource "google_monitoring_alert_policy" "redis_memory" {
  count = var.enable_monitoring ? 1 : 0

  project      = var.project_id
  display_name = "Redis High Memory Usage - ${var.resource_prefix}"
  combiner     = "OR"

  conditions {
    display_name = "Redis memory usage > 80%"

    condition_threshold {
      filter          = "resource.type = \"redis_instance\" AND metric.type = \"redis.googleapis.com/stats/memory/usage_ratio\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email[0].name]

  alert_strategy {
    auto_close = "604800s"
  }
}

resource "google_monitoring_dashboard" "main" {
  project        = var.project_id
  dashboard_json = jsonencode({
    displayName = "IRPF Processor - ${var.environment}"
    gridLayout = {
      columns = 2
      widgets = [
        {
          title = "Cloud Run Request Count"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type = \"cloud_run_revision\" AND metric.type = \"run.googleapis.com/request_count\""
                  aggregation = {
                    alignmentPeriod  = "60s"
                    perSeriesAligner = "ALIGN_RATE"
                  }
                }
              }
            }]
          }
        },
        {
          title = "Cloud Run Request Latency"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type = \"cloud_run_revision\" AND metric.type = \"run.googleapis.com/request_latencies\""
                  aggregation = {
                    alignmentPeriod  = "60s"
                    perSeriesAligner = "ALIGN_PERCENTILE_95"
                  }
                }
              }
            }]
          }
        },
        {
          title = "Redis Memory Usage"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type = \"redis_instance\" AND metric.type = \"redis.googleapis.com/stats/memory/usage_ratio\""
                  aggregation = {
                    alignmentPeriod  = "60s"
                    perSeriesAligner = "ALIGN_MEAN"
                  }
                }
              }
            }]
          }
        },
        {
          title = "Redis Connected Clients"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type = \"redis_instance\" AND metric.type = \"redis.googleapis.com/clients/connected\""
                  aggregation = {
                    alignmentPeriod  = "60s"
                    perSeriesAligner = "ALIGN_MEAN"
                  }
                }
              }
            }]
          }
        }
      ]
    }
  })
}
