resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-${var.resource_prefix}"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "PerGB2018"
  retention_in_days   = var.retention_days

  tags = var.tags
}

resource "azurerm_application_insights" "main" {
  name                = "appi-${var.resource_prefix}"
  resource_group_name = var.resource_group_name
  location            = var.location
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"

  tags = var.tags
}

resource "azurerm_monitor_action_group" "critical" {
  count = var.enable_monitoring ? 1 : 0

  name                = "ag-critical-${var.resource_prefix}"
  resource_group_name = var.resource_group_name
  short_name          = "critical"

  tags = var.tags
}

resource "azurerm_monitor_metric_alert" "api_response_time" {
  count = var.enable_monitoring ? 1 : 0

  name                = "alert-api-response-time-${var.resource_prefix}"
  resource_group_name = var.resource_group_name
  scopes              = [azurerm_application_insights.main.id]
  description         = "Alert when API response time exceeds threshold"
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "microsoft.insights/components"
    metric_name      = "requests/duration"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 5000
  }

  action {
    action_group_id = azurerm_monitor_action_group.critical[0].id
  }

  tags = var.tags
}

resource "azurerm_monitor_metric_alert" "api_failures" {
  count = var.enable_monitoring ? 1 : 0

  name                = "alert-api-failures-${var.resource_prefix}"
  resource_group_name = var.resource_group_name
  scopes              = [azurerm_application_insights.main.id]
  description         = "Alert when API failure rate exceeds threshold"
  severity            = 1
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "microsoft.insights/components"
    metric_name      = "requests/failed"
    aggregation      = "Count"
    operator         = "GreaterThan"
    threshold        = 10
  }

  action {
    action_group_id = azurerm_monitor_action_group.critical[0].id
  }

  tags = var.tags
}
