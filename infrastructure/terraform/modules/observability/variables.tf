variable "resource_group_name" {
  description = "Resource group name"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
}

variable "resource_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "retention_days" {
  description = "Log retention in days"
  type        = number
  default     = 30
}

variable "enable_monitoring" {
  description = "Enable monitoring alerts"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags for resources"
  type        = map(string)
  default     = {}
}
