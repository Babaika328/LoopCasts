#!/usr/bin/env bash
# Clears the TEST data (payments, orders, invoices) so a demo starts clean. The tables stay, only the rows go.
# Run from the project folder:  bash reset-demo.sh        (asks first)
#                               bash reset-demo.sh --yes  (no question)
cd "$(dirname "$0")" || exit 1

if [ "${1:-}" != "--yes" ]; then
  read -r -p "This deletes ALL payments, orders and invoices in the local database. Type yes to continue: " answer
  if [ "$answer" != "yes" ]; then echo "Cancelled."; exit 1; fi
fi

ddev mysql -e "DELETE FROM invoices; DELETE FROM orders; DELETE FROM payments; DELETE FROM invoice_counters; ALTER TABLE orders AUTO_INCREMENT = 1;" \
  && echo "Done. The database is empty and ready for a fresh demo."
