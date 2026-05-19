resource "random_password" "cosmosdb" {
  length  = 32
  special = false
}

resource "azurerm_cosmosdb_account" "main" {
  name                = "cosmos-${var.resource_prefix}"
  resource_group_name = var.resource_group_name
  location            = var.location
  offer_type          = "Standard"
  kind                = "MongoDB"
  
  mongo_server_version = "4.2"

  capabilities {
    name = "EnableMongo"
  }

  capabilities {
    name = "EnableServerless"
  }

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = var.location
    failover_priority = 0
  }

  public_network_access_enabled = false

  tags = var.tags
}

resource "azurerm_cosmosdb_mongo_database" "main" {
  name                = "irpf_processor"
  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.main.name
}

resource "azurerm_cosmosdb_mongo_collection" "documents" {
  name                = "documents"
  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_mongo_database.main.name

  index {
    keys   = ["_id"]
    unique = true
  }

  index {
    keys = ["status"]
  }

  index {
    keys = ["created_at"]
  }
}

resource "azurerm_cosmosdb_mongo_collection" "extractions" {
  name                = "extractions"
  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_mongo_database.main.name

  index {
    keys   = ["_id"]
    unique = true
  }

  index {
    keys = ["document_id"]
  }

  index {
    keys = ["status"]
  }
}

resource "azurerm_private_endpoint" "cosmosdb" {
  name                = "pe-cosmos-${var.resource_prefix}"
  resource_group_name = var.resource_group_name
  location            = var.location
  subnet_id           = var.subnet_id

  private_service_connection {
    name                           = "cosmos-connection"
    private_connection_resource_id = azurerm_cosmosdb_account.main.id
    is_manual_connection           = false
    subresource_names              = ["MongoDB"]
  }

  private_dns_zone_group {
    name                 = "cosmos-dns-zone-group"
    private_dns_zone_ids = [var.private_dns_zone_id]
  }

  tags = var.tags
}
