# Running the project on a new machine

Everything that is code lives in git. These things do not, and are set up by hand on each machine:
the database content (starts empty), the n8n login, the n8n credentials (passwords and keys), and the `.env` file.
Allow about an hour the first time, mostly downloads. Do one full dry run before the defence.

## 1. Install once
Docker Desktop, then on Windows WSL2 with Ubuntu, git, and DDEV inside Ubuntu (see `pre-build-plan.md`).
On Linux or macOS: Docker, git and DDEV directly. For the automatic tests, also inside Ubuntu:
`sudo apt-get install -y python3-pytest`.

## 2. Get the project (inside Ubuntu, in the Linux home folder, not on the Windows desktop)
```bash
git clone <your repository url> ~/LoopCasts
cd ~/LoopCasts
echo "N8N_ENCRYPTION_KEY=$(openssl rand -hex 32)" > n8n/.env
bash start.sh
ddev mysql < db/schema.sql
```
`.ddev/config.yaml` is in git, so DDEV starts with the same PHP version and settings. A new n8n key is fine on a new
machine, because the credentials are created again below. Loading `db/schema.sql` is safe to repeat at any time.

## 3. n8n (open http://localhost:5678)
1. Create the owner account (any email and password, it stays on this machine).
2. Import every file in `n8n/workflows/`: Workflows, then Import from file.
3. Create the credentials (these are the names the nodes expect):

| Name | Type | Values |
|---|---|---|
| MySQL account | MySQL | host `ddev-loopcasts-db`, port `3306`, database `db`, user `db`, password `db`, SSL off |
| Payment simulator | Header Auth | name `Authorization`, value `Bearer test_local_simulator` |
| Members API | Header Auth | name `Authorization`, value `Bearer test_local_members` |
| Mailpit (SMTP) | SMTP | host `ddev-loopcasts-web`, port `1025`, SSL off, no user or password |
| Groq | Groq API | your own API key (never commit it), only needed for the AI step |

4. Open every imported workflow, click each node that shows a credential warning and choose the credential above.
5. In `Payment paid to order`: Settings, Error Workflow, choose `Error alert`.
6. Publish all workflows (the error workflow too). Only published workflows receive webhooks.

The keys `test_local_simulator` and `test_local_members` are development defaults, not secrets. A real deployment sets
`MEMBERS_API_KEY` and friends in the environment (see `.env.example`).

## 4. Check
```bash
bash check.sh          # every line OK
bash test.sh --fast    # site, database, accounts, security: a few minutes
bash test.sh           # everything, including the n8n flow and the emails (longer; the workflows must be published)
```
Open https://loopcasts.ddev.site, order a plan, press Pay, then open Mailpit (`ddev describe` shows its address). You
should see the invoice and the welcome email. Follow the welcome link, choose a password, log in.

The emails of the site itself (password reset) are sent by PHP straight to Mailpit when running in DDEV, with no setup.

## 5. Before a demo
- `bash reset-demo.sh` clears orders, payments, invoices and members. Empty the Mailpit inbox too.
- The AI step needs internet and the Groq key on the machine you show it on.
- DDEV may ask for permission to edit the hosts file once on a new network. Allow it.
- Keep a short screen recording as a fallback.

## If something does not start
- `bash check.sh` says which part is down. Docker Desktop must be running first.
- Port 5678 or 80 already used: stop the other program, or `ddev poweroff` and start again.
- `ddev: command not found` on Windows: you are in PowerShell, open the Ubuntu terminal instead.

## Moving a machine exactly as it is (optional)
Database: `ddev export-db --file=backup.sql.gz` on the old machine and `ddev import-db --file=backup.sql.gz` on the new one.
n8n: the volume `n8n_data` holds workflows, credentials and the n8n login, and it only works together with the same
`N8N_ENCRYPTION_KEY`. Rebuilding from git as above is cleaner, and it is also the proof that someone else can run the project.