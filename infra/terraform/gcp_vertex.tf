# ==============================================================================
# Google Cloud Platform: Vertex AI & Cloud Discovery Engine (1億本記事コーパス)
# ==============================================================================

# 1. IAM Service Account for Vertex AI & Cloud Discovery Engine
resource "google_service_account" "agent_sa" {
  account_id   = "nikkei-rag-vertex-sa"
  display_name = "Nikkei Financial RAG Vertex & Discovery Engine SA"
  description  = "Service account for LangGraph Agent accessing Google Cloud Discovery Engine and Vertex AI"
}

# Grant Vertex AI User role
resource "google_project_iam_member" "vertex_ai_user" {
  project = var.gcp_project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

# Grant Discovery Engine Admin / Viewer role
resource "google_project_iam_member" "discovery_engine_user" {
  project = var.gcp_project_id
  role    = "roles/discoveryengine.viewer"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

# 2. Cloud Discovery Engine Data Store for Nikkei News Articles (1億本超の過去記事検索)
resource "google_discovery_engine_data_store" "nikkei_articles_datastore" {
  location                     = "global"
  data_store_id                = "nikkei-articles-corpus"
  display_name                 = "Nikkei Articles 100M+ Corpus"
  industry_vertical            = "GENERIC"
  content_config               = "CONTENT_REQUIRED"
  solution_types               = ["SOLUTION_TYPE_SEARCH"]
  create_advanced_site_search  = false
}

# 3. Google Cloud Run service as an alternative container deployment
resource "google_cloud_run_v2_service" "financial_rag_cloudrun" {
  name     = "nikkei-financial-rag-service"
  location = var.gcp_region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.agent_sa.email
    scaling {
      min_instance_count = 1 # Keep 1 instance warm for SLO compliance
      max_instance_count = 20
    }

    containers {
      image = "gcr.io/${var.gcp_project_id}/financial-rag-agent:latest"

      resources {
        limits = {
          cpu    = "2"
          memory = "4Gi"
        }
      }

      env {
        name  = "DATA_SOURCE_MODE"
        value = "live_api"
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.gcp_project_id
      }
      env {
        name  = "GCP_LOCATION"
        value = var.gcp_region
      }
      env {
        name  = "DISCOVERY_ENGINE_DATA_STORE_ID"
        value = google_discovery_engine_data_store.nikkei_articles_datastore.data_store_id
      }

      ports {
        container_port = 8000
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}

# Allow unauthenticated invocation for public demo API
resource "google_cloud_run_service_iam_member" "public_access" {
  location = google_cloud_run_v2_service.financial_rag_cloudrun.location
  service  = google_cloud_run_v2_service.financial_rag_cloudrun.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
