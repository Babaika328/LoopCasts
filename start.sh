#!/usr/bin/env bash
# Starts everything: the DDEV site + database, then n8n, then checks that it all answers.
# Run from the project folder:  bash start.sh
set -e
cd "$(dirname "$0")" || exit 1

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Start Docker Desktop, wait for 'Engine running', then run this again."
  exit 1
fi

ddev start
(cd n8n && docker compose up -d)

echo "Waiting for n8n (up to a minute) ..."
for _ in $(seq 1 30); do
  curl -sf http://localhost:5678/healthz >/dev/null 2>&1 && break
  sleep 2
done

echo
bash check.sh || true

echo
echo "Site:  https://loopcasts.ddev.site"
echo "n8n:   http://localhost:5678"
