# LoopCasts automation project

Automation Tools course project — LoopCasts BV, a small Ghent company selling video
trainings about automation. New-hire onboarding + an order-to-cash automation built
on n8n, plus a small website rebuild on the side.

## Status

Planning stage — no workflow built yet. See `pre-build-plan.md` for the current
scope, the evidence behind it, and what's deliberately out of scope.

## What's in this repo

- `handbook-pdf/` — the company's internal handbook (7 chapters), read-only reference.
- `samples/` — small decoded examples of the messy spreadsheet data (colour-coding key etc).
- `dropbox/Courses/course catalogue.xlsx` — course list, used by the website generator.
- `dropbox/Website/site/` — the website source (being rebuilt, see plan).
- `pre-build-plan.md` — the actual plan: priorities, evidence, scope, open questions.
- `firstglance-*.pdf` / `.docx` — week-1 assignment writeups.
- `fixtures/` *(create as needed)* — a handful of hand-picked example emails/invoices
  for testing the intake workflow. Not auto-populated — copy a few in yourself.

## What's deliberately NOT in this repo

Bulk raw data (all order/support emails, all invoice PDFs, the full newsletter list,
the Vimeo export, the bank export) and anything secret (passwords file, DB credentials,
the SQL dump) are excluded via `.gitignore`. Reasons are in the plan doc and in
`.gitignore` itself. Keep that data locally, not in git.

## Quick start

Needs Docker Desktop running, plus WSL2/Ubuntu with DDEV (see `pre-build-plan.md`). From the project folder in Ubuntu:

```bash
bash start.sh        # starts the site, database and n8n, then checks that all of it answers
bash check.sh        # OK / FAIL for every part, exit code 1 if something is down
bash test.sh         # automatic tests: form, payment, webhook, order table (--fast skips the n8n ones)
bash stop.sh         # stops everything, data is kept
bash backup.sh       # dumps the database and proves the dump can be restored
bash reset-demo.sh   # clears the test data before a demo (asks first)
```

- Site: https://loopcasts.ddev.site
- n8n: http://localhost:5678
- Database schema: `db/schema.sql`, load with `ddev mysql < db/schema.sql`
- `.env` files hold secrets locally and are never committed. Copy `.env.example` (root) and `n8n/.env.example` and fill in your own values.

## Where to start

Read `pre-build-plan.md` first — it has the reasoning behind every decision here,
not just the conclusions.