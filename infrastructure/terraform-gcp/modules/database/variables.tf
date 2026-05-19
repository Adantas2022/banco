variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "resource_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "mongodb_atlas_org_id" {
  description = "MongoDB Atlas organization ID"
  type        = string
}

variable "cluster_tier" {
  description = "MongoDB Atlas cluster tier"
  type        = string
  default     = "M10"
}

variable "vpc_network_name" {
  description = "VPC network name for peering"
  type        = string
}

variable "labels" {
  description = "Labels for resources"
  type        = map(string)
  default     = {}
}
