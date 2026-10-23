#!/usr/bin/env bash
# Stops everything. Data is kept (database, n8n workflows).
# Run from the project folder:  bash stop.sh
cd "$(dirname "$0")" || exit 1
(cd n8n && docker compose stop)
ddev stop
