#!/usr/bin/env bash
# Checks that every part of the project answers. Prints OK or FAIL for each part and
# exits with 1 if anything failed, so a broken part is never silent.
# Run from the project folder:  bash check.sh
cd "$(dirname "$0")" || exit 1
failed=0

check() {
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then
    printf '  OK    %s\n' "$name"
  else
    printf '  FAIL  %s\n' "$name"
    failed=1
  fi
}

last() { tail -n 1 | tr -d '\r'; }   # ddev sometimes prints tips; only the last line counts

docker_up()    { docker info; }
site_up()      { [ "$(ddev exec curl -s -o /dev/null -w '%{http_code}' http://localhost/ | last)" = "200" ]; }
db_up()        { [ "$(ddev mysql -N -e 'SELECT 1' | last)" = "1" ]; }
tables_ok()    { [ "$(ddev mysql -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='db' AND table_name IN ('payments','orders','invoices','invoice_counters')" | last)" = "4" ]; }
api_up()       { [ "$(ddev exec curl -s -o /dev/null -w '%{http_code}' -H 'Authorization: Bearer test_local_simulator' 'http://localhost/pay/api.php?id=none' | last)" = "404" ]; }
n8n_up()       { curl -sf http://localhost:5678/healthz; }
n8n_to_site()  { docker exec n8n wget -qO- 'http://ddev-loopcasts-web/pay/api.php?id=none' 2>&1 | grep -q Unauthorized; }
site_to_n8n()  { ddev exec curl -sf http://n8n:5678/healthz; }

echo "Checking LoopCasts ..."
check "Docker is running"                      docker_up
check "Site answers (DDEV web)"                site_up
check "Database answers"                       db_up
check "Database has the four tables"           tables_ok
check "Payment simulator API accepts its key"  api_up
check "n8n answers on localhost:5678"          n8n_up
check "n8n can reach the site"                 n8n_to_site
check "Site can reach n8n (webhook path)"      site_to_n8n

echo
if [ "$failed" -eq 0 ]; then
  echo "All good."
else
  echo "Something is down. Try:  bash start.sh"
  exit 1
fi
