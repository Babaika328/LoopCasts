#!/usr/bin/env bash
# Runs the automatic tests.
#   bash test.sh          all tests (about a minute); needs the n8n workflow "Payment paid to order" ACTIVE
#   bash test.sh --fast   skips the tests that wait for n8n
cd "$(dirname "$0")" || exit 1

if ! python3 -c "import pytest" 2>/dev/null; then
  echo "pytest is missing. Install it once with:  sudo apt-get install -y python3-pytest"
  exit 1
fi

bash check.sh || { echo; echo "The stack is not healthy. Fix that first."; exit 1; }
echo

if [ "${1:-}" = "--fast" ]; then
  python3 -m pytest -q -m "not n8n"
else
  python3 -m pytest -q
fi
