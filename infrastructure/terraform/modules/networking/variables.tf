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

variable "vnet_address_space" {
  description = "VNet address space"
  type        = list(string)
}

variable "subnet_prefixes" {
  description = "Subnet address prefixes"
  type = object({
    container_apps    = string
    database          = string
    cache             = string
    private_endpoints = string
  })
}

variable "tags" {
  description = "Tags for resources"
  type        = map(string)
  default     = {}
}
