#!/usr/bin/env bash
# Backs up the database AND proves the backup can be restored (the handbook's backups were never restore-tested).
# Run from the project folder:  bash backup.sh
# Backups go to backups/ (gitignored, they hold data). The 14 newest are kept.
cd "$(dirname "$0")" || exit 1
mkdir -p backups
stamp=$(date +%Y%m%d-%H%M%S)
file="backups/loopcasts-$stamp.sql.gz"
last() { tail -n 1 | tr -d '\r'; }

echo "Dumping the database to $file ..."
if ! ddev export-db --file="$file" >/dev/null 2>&1; then
  echo "FAIL  dump failed. Is DDEV running? Try: bash start.sh"
  exit 1
fi
if ! gzip -t "$file"; then echo "FAIL  the dump file is damaged"; exit 1; fi
size=$(wc -c < "$file")
if [ "$size" -lt 500 ]; then echo "FAIL  the dump is suspiciously small ($size bytes)"; exit 1; fi
echo "OK    dump written ($size bytes)"

echo "Restore check: loading the dump into a scratch database ..."
root() { ddev mysql -uroot -proot "$@"; }
root -e "DROP DATABASE IF EXISTS restore_check; CREATE DATABASE restore_check;" >/dev/null 2>&1 \
  || { echo "FAIL  could not create the scratch database (the dump itself is saved)"; exit 2; }
gunzip -c "$file" | root restore_check >/dev/null 2>&1 \
  || { echo "FAIL  the dump could not be loaded back"; root -e "DROP DATABASE IF EXISTS restore_check;" >/dev/null 2>&1; exit 2; }

t_live=$(ddev mysql -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='db'" | last)
t_back=$(root -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='restore_check'" | last)
o_live=$(ddev mysql -N -e "SELECT COUNT(*) FROM db.orders" | last)
o_back=$(root -N -e "SELECT COUNT(*) FROM restore_check.orders" | last)
root -e "DROP DATABASE IF EXISTS restore_check;" >/dev/null 2>&1

if [ "$t_live" = "$t_back" ] && [ "$o_live" = "$o_back" ]; then
  echo "OK    restore check passed ($t_back tables, $o_back orders)"
else
  echo "FAIL  restored copy differs: tables $t_live vs $t_back, orders $o_live vs $o_back"
  exit 2
fi

ls -1t backups/loopcasts-*.sql.gz 2>/dev/null | tail -n +15 | xargs -r rm --
echo "Done."
