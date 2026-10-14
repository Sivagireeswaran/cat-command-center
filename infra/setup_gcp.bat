gcloud auth login
gcloud auth application-default login
gcloud config set project project-25d79606-d901-4e5c-80a

gcloud services enable aiplatform.googleapis.com bigquery.googleapis.com ^
  pubsub.googleapis.com run.googleapis.com documentai.googleapis.com ^
  discoveryengine.googleapis.com storage.googleapis.com ^
  artifactregistry.googleapis.com cloudbuild.googleapis.com sqladmin.googleapis.com

gcloud pubsub topics create hazard-events
gcloud pubsub topics create claims-fnol
gcloud storage buckets create gs://project-25d79606-d901-4e5c-80a-cat-assets --location=asia-south1
bq --location=asia-south1 mk --dataset project-25d79606-d901-4e5c-80a:cat_insurance