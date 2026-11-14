terraform {
  required_version = ">= 1.5"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
  resource_provider_registrations = "none"
}

data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "project" {
  name     = "rg-fraud-detection"
  location = "spaincentral"

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_storage_account" "lake" {
  name                            = var.storage_account_name
  resource_group_name             = azurerm_resource_group.project.name
  location                        = azurerm_resource_group.project.location
  account_kind                    = "StorageV2"
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  is_hns_enabled                  = true
  allow_nested_items_to_be_public = false
  min_tls_version                 = "TLS1_2"

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_storage_container" "data" {
  name                  = "fraud-data"
  storage_account_id    = azurerm_storage_account.lake.id
  container_access_type = "private"

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_key_vault" "project" {
  name                       = var.key_vault_name
  resource_group_name        = azurerm_resource_group.project.name
  location                   = azurerm_resource_group.project.location
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  soft_delete_retention_days = 90

  lifecycle {
    prevent_destroy = true
  }
}

variable "storage_account_name" {
  description = "Nom Azure globalement unique du compte ADLS."
  type        = string
  default     = "stfrauddetection1234"
}

variable "key_vault_name" {
  description = "Nom Azure globalement unique du coffre Key Vault."
  type        = string
  default     = "kv-fraud-detection-1234"
}
