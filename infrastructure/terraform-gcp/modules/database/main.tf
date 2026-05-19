resource "mongodbatlas_project" "main" {
  name   = "irpf-processor-${var.environment}"
  org_id = var.mongodb_atlas_org_id
}

resource "random_password" "mongodb" {
  length  = 24
  special = false
}

resource "mongodbatlas_database_user" "main" {
  username           = "irpf-processor"
  password           = random_password.mongodb.result
  project_id         = mongodbatlas_project.main.id
  auth_database_name = "admin"

  roles {
    role_name     = "readWrite"
    database_name = "irpf_processor"
  }

  scopes {
    name = mongodbatlas_cluster.main.name
    type = "CLUSTER"
  }
}

resource "mongodbatlas_cluster" "main" {
  project_id = mongodbatlas_project.main.id
  name       = "cluster-${var.resource_prefix}"

  provider_name               = "GCP"
  provider_region_name        = local.atlas_region
  provider_instance_size_name = var.cluster_tier

  cluster_type = "REPLICASET"

  mongo_db_major_version = "7.0"

  auto_scaling_compute_enabled                    = var.cluster_tier != "M10"
  auto_scaling_compute_scale_down_enabled         = var.cluster_tier != "M10"
  provider_auto_scaling_compute_min_instance_size = var.cluster_tier
  provider_auto_scaling_compute_max_instance_size = var.cluster_tier == "M10" ? "M10" : "M40"

  backup_enabled = true

  pit_enabled = var.environment == "prod"

  advanced_configuration {
    javascript_enabled = false
  }

  labels {
    key   = "environment"
    value = var.environment
  }
}

resource "mongodbatlas_network_container" "main" {
  project_id       = mongodbatlas_project.main.id
  atlas_cidr_block = "192.168.0.0/21"
  provider_name    = "GCP"
}

resource "mongodbatlas_network_peering" "main" {
  project_id     = mongodbatlas_project.main.id
  container_id   = mongodbatlas_network_container.main.id
  provider_name  = "GCP"
  gcp_project_id = var.project_id
  network_name   = var.vpc_network_name
}

resource "mongodbatlas_project_ip_access_list" "gcp" {
  project_id = mongodbatlas_project.main.id
  cidr_block = "10.0.0.0/8"
  comment    = "GCP VPC CIDR"
}

locals {
  atlas_region = lookup({
    "southamerica-east1" = "SOUTH_AMERICA_EAST_1"
    "us-central1"        = "CENTRAL_US"
    "us-east1"           = "EASTERN_US"
    "us-west1"           = "WESTERN_US"
    "europe-west1"       = "WESTERN_EUROPE"
  }, var.region, "SOUTH_AMERICA_EAST_1")
}
