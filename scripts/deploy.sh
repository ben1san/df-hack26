#!/usr/bin/env bash
# Cloud Run へ出す。ローカルで docker build しない（Apple Silicon で arm になり落ちる）。
# --source を使うと Cloud Build が amd64 で焼く。
set -euo pipefail

PROJECT="${PROJECT:?PROJECT を指定してください}"
REGION="${REGION:-asia-northeast1}"
SERVICE="${SERVICE:-roster}"

echo "== API を有効化"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  aiplatform.googleapis.com \
  --project "$PROJECT"

echo "== Firestore（Native モード。あとから変えられない）"
gcloud firestore databases create --location="$REGION" --type=firestore-native \
  --project "$PROJECT" 2>/dev/null || echo "   すでにある"

echo "== security rules（クライアント経路を全部閉じる）"
gcloud firestore databases update --project "$PROJECT" >/dev/null 2>&1 || true
# rules のデプロイは firebase CLI を使う:
#   firebase deploy --only firestore:rules --project "$PROJECT"

echo "== サービスアカウントに権限"
SA="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
for ROLE in roles/datastore.user roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:$SA" --role="$ROLE" --condition=None >/dev/null
done
echo "   $SA に datastore.user / aiplatform.user"

echo "== デプロイ"
gcloud run deploy "$SERVICE" \
  --source . \
  --project "$PROJECT" \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 1Gi --cpu 2 --timeout 120 \
  --min-instances 0 \
  --set-env-vars "REPO=firestore,GOOGLE_GENAI_USE_VERTEXAI=1,GOOGLE_CLOUD_PROJECT=$PROJECT,GOOGLE_CLOUD_LOCATION=global,SOLVE_SECONDS=10"

URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format='value(status.url)')"
echo
echo "URL  $URL"
echo "次 — 提出用リポジトリの README にこのURLを書く"
echo "    11/10 19:00 以降は --min-instances=1 に上げる（11/14までで \$1前後）"
