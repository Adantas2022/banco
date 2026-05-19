resource "google_compute_network" "main" {
  name                    = "vpc-${var.resource_prefix}"
  project                 = var.project_id
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

resource "google_compute_subnetwork" "cloudrun" {
  name          = "subnet-cloudrun-${var.resource_prefix}"
  project       = var.project_id
  region        = var.region
  network       = google_compute_network.main.id
  ip_cidr_range = var.subnet_ranges.cloudrun

  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

resource "google_compute_subnetwork" "serverless_vpc" {
  name          = "subnet-serverless-${var.resource_prefix}"
  project       = var.project_id
  region        = var.region
  network       = google_compute_network.main.id
  ip_cidr_range = var.subnet_ranges.serverless_vpc

  private_ip_google_access = true
}

resource "google_vpc_access_connector" "main" {
  name          = "vpc-con-${var.resource_prefix}"
  project       = var.project_id
  region        = var.region
  network       = google_compute_network.main.name
  ip_cidr_range = var.subnet_ranges.serverless_vpc
  min_instances = 2
  max_instances = 10

  machine_type = "e2-micro"
}

resource "google_compute_global_address" "private_services" {
  name          = "private-services-${var.resource_prefix}"
  project       = var.project_id
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main.id
}

resource "google_service_networking_connection" "private_services" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_services.name]
}

resource "google_compute_firewall" "allow_internal" {
  name    = "fw-allow-internal-${var.resource_prefix}"
  project = var.project_id
  network = google_compute_network.main.name

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = [var.vpc_cidr]
}

resource "google_compute_firewall" "allow_health_check" {
  name    = "fw-allow-health-check-${var.resource_prefix}"
  project = var.project_id
  network = google_compute_network.main.name

  allow {
    protocol = "tcp"
    ports    = ["8000", "8080"]
  }

  source_ranges = ["130.211.0.0/22", "35.191.0.0/16"]
  target_tags   = ["allow-health-check"]
}

resource "google_compute_router" "main" {
  name    = "router-${var.resource_prefix}"
  project = var.project_id
  region  = var.region
  network = google_compute_network.main.id
}

resource "google_compute_router_nat" "main" {
  name                               = "nat-${var.resource_prefix}"
  project                            = var.project_id
  router                             = google_compute_router.main.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
