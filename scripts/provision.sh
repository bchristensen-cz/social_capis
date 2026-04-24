#!/usr/bin/env bash
# One-time provisioning for social-capis on GCP.
# Run from any shell with `gcloud` authenticated to the target project.
#
# Pre-req: `gcloud auth login` and be the Owner or Editor of the project.
# This script is idempotent: re-running it is safe — creates are guarded.

set -euo pipefail

# ---------- Config ----------
PROJECT="marketing-data-442316"
REGION="us-central1"
BQ_DATASET="sales_ops"

JOB_NAME="social-capis-daily"
AR_REPO="social-capis"
JOB_SA="social-capis-job"
SCHED_SA="social-capis-scheduler"
SECRETS=(
  tiktok-access-token
  tiktok-pixel-code
  meta-access-token
  meta-dataset-id
  snap-access-token
  snap-pixel-id
  github-pat
)
# ----------------------------

JOB_SA_EMAIL="${JOB_SA}@${PROJECT}.iam.gserviceaccount.com"
SCHED_SA_EMAIL="${SCHED_SA}@${PROJECT}.iam.gserviceaccount.com"

echo "==> project=${PROJECT} region=${REGION}"
gcloud config set project "$PROJECT" >/dev/null

echo "==> enabling APIs"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  bigquery.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  cloudscheduler.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com

echo "==> artifact registry repo: ${AR_REPO}"
gcloud artifacts repositories describe "$AR_REPO" --location="$REGION" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "$AR_REPO" \
    --repository-format=docker \
    --location="$REGION" \
    --description="social_capis container images"

echo "==> service account: ${JOB_SA_EMAIL}"
gcloud iam service-accounts describe "$JOB_SA_EMAIL" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "$JOB_SA" \
    --display-name="social-capis Cloud Run Job runtime"

echo "==> service account: ${SCHED_SA_EMAIL}"
gcloud iam service-accounts describe "$SCHED_SA_EMAIL" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "$SCHED_SA" \
    --display-name="social-capis Cloud Scheduler invoker"

echo "==> IAM: BigQuery + logging + monitoring on job SA"
for role in \
  roles/bigquery.dataViewer \
  roles/bigquery.jobUser \
  roles/logging.logWriter \
  roles/monitoring.metricWriter; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:${JOB_SA_EMAIL}" \
    --role="$role" \
    --condition=None >/dev/null
done

echo "==> (optional, scoped) BigQuery dataset-level viewer is sufficient; project-level binding above is fine for MVP."
echo "    Tighten later with: bq show --format=prettyjson ${PROJECT}:${BQ_DATASET} | ..."

echo "==> creating Secret Manager entries (empty placeholders)"
for s in "${SECRETS[@]}"; do
  gcloud secrets describe "$s" >/dev/null 2>&1 || \
    gcloud secrets create "$s" --replication-policy=automatic
  gcloud secrets add-iam-policy-binding "$s" \
    --member="serviceAccount:${JOB_SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None >/dev/null
done

echo "==> scheduler SA: run.invoker (will be scoped to the Job after first deploy)"
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${SCHED_SA_EMAIL}" \
  --role="roles/run.invoker" \
  --condition=None >/dev/null

cat <<EOF

==============================================================================
DONE.

Next steps:

1. Add values to the 7 secrets (one-off, interactive):

   for NAME in tiktok-access-token tiktok-pixel-code meta-access-token \\
               meta-dataset-id snap-access-token snap-pixel-id github-pat; do
     read -s -p "\$NAME: " V
     echo
     echo -n "\$V" | gcloud secrets versions add "\$NAME" --data-file=-
   done

2. First Cloud Build run (manual):

   gcloud builds submit --config=cloudbuild.yaml \\
     --substitutions=SHORT_SHA=manual-\$(date +%s),_REGION=${REGION},_JOB_NAME=${JOB_NAME}

   If the Job doesn't exist yet, first deploy it:

   gcloud run jobs deploy ${JOB_NAME} \\
     --image=${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}/job:latest \\
     --region=${REGION} \\
     --service-account=${JOB_SA_EMAIL} \\
     --set-env-vars=GCP_PROJECT=${PROJECT},BQ_DATASET=${BQ_DATASET},GITHUB_REPO=bchristensen-cz/social_capis,DRY_RUN=true,TZ=America/Denver \\
     --set-secrets=TIKTOK_ACCESS_TOKEN=tiktok-access-token:latest,TIKTOK_PIXEL_CODE=tiktok-pixel-code:latest,META_ACCESS_TOKEN=meta-access-token:latest,META_DATASET_ID=meta-dataset-id:latest,SNAP_ACCESS_TOKEN=snap-access-token:latest,SNAP_PIXEL_ID=snap-pixel-id:latest,GITHUB_PAT=github-pat:latest \\
     --max-retries=1 --task-timeout=1800s --cpu=1 --memory=1Gi

3. Test a DRY_RUN execution:

   gcloud run jobs execute ${JOB_NAME} --region=${REGION} --wait

4. Flip DRY_RUN=false, then create the Scheduler cron (04:00 MT):

   gcloud run jobs update ${JOB_NAME} --region=${REGION} --update-env-vars=DRY_RUN=false

   gcloud scheduler jobs create http ${JOB_NAME}-cron \\
     --location=${REGION} \\
     --schedule="0 4 * * *" --time-zone="America/Denver" \\
     --uri="https://run.googleapis.com/v2/projects/${PROJECT}/locations/${REGION}/jobs/${JOB_NAME}:run" \\
     --http-method=POST \\
     --oauth-service-account-email=${SCHED_SA_EMAIL}

5. Connect the Cloud Build GitHub trigger (one-time, via console or gcloud):

   https://console.cloud.google.com/cloud-build/triggers?project=${PROJECT}

   - Event: Push to a branch
   - Source: bchristensen-cz/social_capis
   - Branch: ^main$
   - Build config: cloudbuild.yaml
==============================================================================
EOF
