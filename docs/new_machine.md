# Running the project on a new machine

Everything that is code lives in git. Four things do not, and are set up by hand on each machine:
the database content (starts empty), the n8n login, the n8n credentials (passwords and keys), and the `.env` file.
Allow about an hour the first time, mostly downloads. Do a full dry run once before the defence.

## 1. Install once
Docker Desktop, then on Windows WSL2 with Ubuntu, git, and DDEV inside Ubuntu (see `pre-build-plan.md`).
On Linux or macOS: Docker, git and DDEV directly.

## 2. Get the project (inside Ubuntu, in the Linux home folder, not on the Windows desktop)
```bash
git clone <your repository url> ~/LoopCasts
cd ~/LoopCasts
echo "N8N_ENCRYPTION_KEY=$(openssl rand -hex 32)" > n8n/.env
bash start.sh
ddev mysql < db/schema.sql
```
A new key is fine on a new machine, because credentials are created again below.

## 3. n8n (open http://localhost:5678)
1. Create the owner account (any email and password, it stays on this machine).
2. Import the workflows: Workflows, then Import from file, for every file in `n8n/workflows/`.
3. Create the credentials (these names are what the nodes expect):

| Name | Type | Values |
|---|---|---|
| MySQL account | MySQL | host `ddev-loopcasts-db`, port `3306`, database `db`, user `db`, password `db`, SSL off |
| Payment simulator | Header Auth | name `Authorization`, value `Bearer test_local_simulator` |
| Mailpit (SMTP) | SMTP | host `ddev-loopcasts-web`, port `1025`, SSL off, no user or password |
| Groq | Groq API | your own API key (never commit it) |

4. Open every imported workflow, click each node that shows a credential warning and choose the credential above.
5. In `Payment paid to order`: Settings, Error Workflow, choose `Error alert`.
6. Publish both workflows (`Error alert` too).

## 4. Check
```bash
bash check.sh      # every line OK
bash test.sh       # everything green
```
Open the site at https://loopcasts.ddev.site, order a plan, press Pay, and look at Mailpit (`ddev describe` shows its address).

## 5. Before a demo
- `bash reset-demo.sh` clears the test orders and payments. Empty the Mailpit inbox.
- The AI step needs internet and the Groq key on the machine you show it on.
- DDEV may ask for permission to edit the hosts file once on a new network. Allow it.
- Keep a short screen recording as a fallback.

## Moving a machine exactly as it is (optional)
Database: `ddev export-db --file=backup.sql.gz` on the old machine and `ddev import-db --file=backup.sql.gz` on the new one.
n8n: the volume `n8n_data` holds workflows, credentials and the n8n login, and it only works together with the same
`N8N_ENCRYPTION_KEY`. Rebuilding from git as above is cleaner, and it is also the proof that someone else can run the project.