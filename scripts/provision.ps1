# One-time provisioning for social-capis on GCP.
# Run from PowerShell with gcloud authenticated to the target project.
#
# Pre-req: `gcloud auth login` and be Owner/Editor of the project.
# This script is idempotent: safe to re-run.

$ErrorActionPreference = 'Stop'

# ---------- Config ----------
$Project   = 'marketing-data-442316'
$Region    = 'us-central1'
$BqDataset = 'sales_ops'

$JobName  = 'social-capis-daily'
$ArRepo   = 'social-capis'
$JobSa    = 'social-capis-job'
$SchedSa  = 'social-capis-scheduler'
$Secrets  = @(
    'tiktok-access-token',
    'tiktok-pixel-code',
    'meta-access-token',
    'meta-dataset-id',
    'snap-access-token',
    'snap-pixel-id',
    'github-pat'
)
# ----------------------------

$JobSaEmail   = "$JobSa@$Project.iam.gserviceaccount.com"
$SchedSaEmail = "$SchedSa@$Project.iam.gserviceaccount.com"

function Invoke-Gcloud {
    # Run gcloud; throw if it fails. Avoids PowerShell's flaky handling of native stderr.
    $args = $args
    & gcloud @args
    if ($LASTEXITCODE -ne 0) { throw "gcloud failed (exit $LASTEXITCODE): $($args -join ' ')" }
}

function Test-GcloudResource {
    # Returns $true when the describe-style gcloud command succeeds, $false on non-zero exit.
    & gcloud @args *> $null
    return ($LASTEXITCODE -eq 0)
}

Write-Host "==> project=$Project region=$Region"
Invoke-Gcloud config set project $Project | Out-Null

Write-Host "==> enabling APIs"
Invoke-Gcloud services enable `
    run.googleapis.com `
    cloudbuild.googleapis.com `
    bigquery.googleapis.com `
    secretmanager.googleapis.com `
    artifactregistry.googleapis.com `
    cloudscheduler.googleapis.com `
    logging.googleapis.com `
    monitoring.googleapis.com

Write-Host "==> artifact registry repo: $ArRepo"
if (-not (Test-GcloudResource artifacts repositories describe $ArRepo --location=$Region)) {
    Invoke-Gcloud artifacts repositories create $ArRepo `
        --repository-format=docker `
        --location=$Region `
        --description='social_capis container images'
}

Write-Host "==> service account: $JobSaEmail"
if (-not (Test-GcloudResource iam service-accounts describe $JobSaEmail)) {
    Invoke-Gcloud iam service-accounts create $JobSa `
        --display-name='social-capis Cloud Run Job runtime'
}

Write-Host "==> service account: $SchedSaEmail"
if (-not (Test-GcloudResource iam service-accounts describe $SchedSaEmail)) {
    Invoke-Gcloud iam service-accounts create $SchedSa `
        --display-name='social-capis Cloud Scheduler invoker'
}

Write-Host "==> IAM: BigQuery + logging + monitoring on job SA"
$roles = @(
    'roles/bigquery.dataViewer',
    'roles/bigquery.jobUser',
    'roles/logging.logWriter',
    'roles/monitoring.metricWriter'
)
foreach ($role in $roles) {
    Invoke-Gcloud projects add-iam-policy-binding $Project `
        --member="serviceAccount:$JobSaEmail" `
        --role=$role `
        --condition=None | Out-Null
}

Write-Host "==> creating Secret Manager entries (empty placeholders)"
foreach ($s in $Secrets) {
    if (-not (Test-GcloudResource secrets describe $s)) {
        Invoke-Gcloud secrets create $s --replication-policy=automatic
    }
    Invoke-Gcloud secrets add-iam-policy-binding $s `
        --member="serviceAccount:$JobSaEmail" `
        --role='roles/secretmanager.secretAccessor' `
        --condition=None | Out-Null
}

Write-Host "==> scheduler SA: run.invoker"
Invoke-Gcloud projects add-iam-policy-binding $Project `
    --member="serviceAccount:$SchedSaEmail" `
    --role='roles/run.invoker' `
    --condition=None | Out-Null

@"

==============================================================================
DONE.

Next steps:

1. Add values to the 7 secrets (one-off, interactive):

   `$names = 'tiktok-access-token','tiktok-pixel-code','meta-access-token',``
            'meta-dataset-id','snap-access-token','snap-pixel-id','github-pat'
   foreach (`$n in `$names) {
     `$v = Read-Host -AsSecureString -Prompt `$n
     `$plain = [System.Net.NetworkCredential]::new('', `$v).Password
     `$plain | gcloud secrets versions add `$n --data-file=-
   }

2. First deploy of the Job (DRY_RUN=true for validation):

   gcloud run jobs deploy $JobName ``
     --image=$Region-docker.pkg.dev/$Project/$ArRepo/job:latest ``
     --region=$Region ``
     --service-account=$JobSaEmail ``
     --set-env-vars=GCP_PROJECT=$Project,BQ_DATASET=$BqDataset,GITHUB_REPO=bchristensen-cz/social_capis,DRY_RUN=true,TZ=America/Denver ``
     --set-secrets=TIKTOK_ACCESS_TOKEN=tiktok-access-token:latest,TIKTOK_PIXEL_CODE=tiktok-pixel-code:latest,META_ACCESS_TOKEN=meta-access-token:latest,META_DATASET_ID=meta-dataset-id:latest,SNAP_ACCESS_TOKEN=snap-access-token:latest,SNAP_PIXEL_ID=snap-pixel-id:latest,GITHUB_PAT=github-pat:latest ``
     --max-retries=1 --task-timeout=1800s --cpu=1 --memory=1Gi

   (The image doesn't exist yet — run Cloud Build first, then this deploy command.)

3. First Cloud Build (manual build of the current commit):

   gcloud builds submit --config=cloudbuild.yaml

4. Execute a dry run:

   gcloud run jobs execute $JobName --region=$Region --wait

5. Flip to live + create Scheduler cron (04:00 MT):

   gcloud run jobs update $JobName --region=$Region --update-env-vars=DRY_RUN=false

   gcloud scheduler jobs create http $JobName-cron ``
     --location=$Region ``
     --schedule='0 4 * * *' --time-zone='America/Denver' ``
     --uri="https://run.googleapis.com/v2/projects/$Project/locations/$Region/jobs/${JobName}:run" ``
     --http-method=POST ``
     --oauth-service-account-email=$SchedSaEmail

6. Connect Cloud Build GitHub trigger (one-time, via console):

   https://console.cloud.google.com/cloud-build/triggers?project=$Project
   - Event: Push to a branch
   - Source: bchristensen-cz/social_capis
   - Branch: ^main$
   - Build config: cloudbuild.yaml
==============================================================================
"@
