# LoopCasts — pre-build plan

Before touching anything: what to automate, why (with numbers, not gut feeling), what to deliberately leave alone, and what's still an open question for day one.

## The numbers that changed the priority order

A `samples/` folder in the data turned out to hold a decoded key for the colour-only status fields used throughout the real spreadsheets. Applying that key to the full dataset (not just the 30-row sample) produced numbers Marieke doesn't currently have herself:

- **Payment status, recalculated for real:** of 282 invoices, 206 are confirmed paid (green), 6 are confirmed *underpaid* (orange, €1,750 short), and **70 have no status colour at all — €11,932 genuinely unconfirmed.** Total not-confirmed-paid: **≈ €13,682**. Marieke's own estimate in the handbook: *"I think about €4,000 is open, but I would have to count."* The real number is **more than 3x that.**
- **VAT reverse-charge is being missed systematically, not just once.** The handbook describes one caught case (Bakker Automatisering, fixed after the fact with a credit note). Checking every foreign customer with a valid EU VAT number against what was actually invoiced found **6 such cases total — 5 of them still sitting wrong**, unnoticed.
- **Renewal / churn, quantified:** of 397 customers who bought a yearly subscription in 2025, only **73 (18.4%)** show up again in the 2026 orders data (through October). This is the number behind Yasmine's wish: *"Who of our customers is about to leave... we never put them together."* Even allowing for some being simply not yet due, this is a large, currently invisible gap.
- **The `account_created` colour flag covers 208 of 300 orders (69%)** in `orders 2026.xlsx`, but neither the handbook nor the data says which way it points — the samples key gives the colour's *name*, not its *meaning*. I checked for a pattern by product type and by time; none found. **This one is not decoded — it's an open question, see below.**
- Team-licence seat members (21 orders) are recorded as **Excel cell comments**, invisible unless you hover over the cell, and several are marked *"rest follows"* with no sign the rest ever arrived.
- **Bank payment references are usable far less often than assumed — checked, not guessed.** Of 1,450 incoming payments in the KBC export, only **276 (19%) carry any matchable invoice or subscription reference.** 956 (66%) have nothing but a generic word ("loopcasts", "abonnement") or a blank field. This is the real reason rule-based matching (invoice number only) can't do the job alone — it directly justifies a fuzzy/AI matching step in the design, not just a "nice to have."
- **All 136 invoice PDFs checked for calculation errors, not just a sample** — confirms exactly one (2026-0005, the known €180.92-vs-€180.29 case). No others found.

*Correction from an earlier pass:* I originally said the 46 newsletter unsubscribe replies were "never removed" from the master list. Checked properly by matching actual sender addresses against the list: of 45 unique senders, **16 are still on it, 29 were correctly removed.** Real gap, smaller than first claimed — noting the correction rather than leaving the overstated version standing.

## What changes, what doesn't

Three points: rebuild the website (it's bad), move off Excel into a real database eventually, and AI can automate the emails as long as a human checks it.

- **AI + human-review for emails** — no change needed, this is already the design (order-intake parsing, support triage both keep a human-approval step, specifically because of the phishing email found in the support inbox).
- **Excel → database** — agreed, and it's not a separate project: if the order-intake workflow writes to a real table instead of `orders 2026.xlsx` from day one, the database is a side effect of building order-to-cash correctly (a unique constraint kills the duplicate-invoice-number problem outright; a proper status column kills the colour-with-no-legend problem outright). Migrating the *historical* 2025/2026 Excel data into that table is separate, lower-priority work — it means re-solving every formatting mess (five date formats, three ways to write "Belgium") as a one-time cleanup pass, not an ongoing workflow.
- **Website rebuild** — agreed in part, needs splitting before it becomes a task. "The website" is two very different things: the static marketing pages (chaotic, but low-risk to redo — this is where git + CI/CD, week 3–4 material, actually belongs) and the members-area login/MySQL app (the SQL-injection/hardcoded-password one). The handbook's own "we do not touch it" and "no test site" apply specifically to the second one. Rebuilding the front pages is reasonable scope; folding the members-area into the same rebuild without a staging environment first would just move the security risk instead of fixing it. Worth asking the instructor directly whether "the website" means both, since that changes the size of the task a lot.

## Roadmap beyond the 12-week project (not core, but now written down so it isn't lost)

The website rebuild is now a confirmed, separate initiative (instructor's call), not just a "someday." Decided approach, kept deliberately simple:

- **Marketing + course pages (54 pages):** stop hand-writing them. One template + a small generator script that builds every page from the course catalogue data (Excel now, the new database later). This is the direct fix for Tom's *"never copy-pasting a video page again"* and for the retired/draft courses still showing live — a page simply won't generate if the status isn't `live`. Can later be wired as its own small n8n workflow: catalogue change → regenerate → git push → CI deploy, which keeps the rebuild inside the same automation story instead of being an unrelated web project.
- **Members-area (login + video access):** rebuild in **plain PHP, not a framework** — decided after weighing Laravel against the team's actual situation. PDO with prepared statements (kills the SQL injection) and `password_hash()`/`password_verify()` (kills the unsalted-MD5 problem) closes both real vulnerabilities in a few dozen lines. A full framework (Laravel) would fix the same things out of the box, but adds a dependency surface (composer, migrations, framework upgrades) nobody at a 5-person company is positioned to maintain — likely trading today's "nobody understands this script" for the same sentence about a bigger codebase in three years. Simpler and more reliable wins here.
- **Tooling:** `ddev` for local dev (already standard for week 3+ of the course, Docker-based, no local PHP/MySQL install pain), `git` + GitHub Actions for CI/CD deploys (replacing manual FTP entirely), `ngrok` used narrowly — a temporary public tunnel when a webhook (e.g. the order-intake form) needs to be reachable from outside while still running locally in ddev, or for a live demo. Not part of how the site is actually hosted.
- **Staging first.** Currently "if it's broken, it's broken live" — nothing above goes live without a real staging environment first, especially the members-area rewrite.
- **Database:** stays MySQL/MariaDB to match the current export and whatever the existing host actually supports, run locally through ddev. Historical order/invoice data (2025 + 2026, ~1,000 rows) gets migrated in a separate cleanup pass — not bundled into the rebuild — since it means re-solving the date/country/price format mess as a one-time job, not an ongoing workflow concern.

## The plan: one process, not five separate projects

Order intake → invoicing → payment matching are one process (order-to-cash), and the project format wants exactly that: *"one complete process chain, from analysis to a working, documented automation."* Building three separate mini-projects would be the wrong shape for the rubric and wouldn't fix anything end-to-end.

**Scope:**
1. Webhook-based order form replaces the `mailto:` link (kills the freeform-text root cause; AI step parses/validates).
2. Order writes a structured row **into a real table, not `orders 2026.xlsx`** (a unique constraint alone kills the duplicate-invoice-number problem).
3. **Invoice generation, VAT reverse-charge logic, and bank payment matching are delegated to a Belgian invoicing API (Billit or Yuki — to shortlist and pick one), not built by hand in n8n.** n8n's job becomes: call the API to create the invoice, receive its payment-confirmed webhook, and flag whatever the API itself can't resolve. Reasoning: we've already found the exact two mistakes a hand-built version would risk repeating — a duplicated invoice number and 5 missed reverse-charge cases — and getting invoice numbering and VAT rules right is literally the business these services exist for. Most of these also handle the bank side themselves (PSD2 connection, incl. KBC), which removes Marieke's Friday manual export entirely, not just the matching step.
4. Error handling: anything the AI parser can't confidently fill in on intake, or anything the invoicing API itself can't match/resolve, goes to a human — not silently dropped and not silently auto-approved.

This one chain, done properly, closes three of the five original pain points completely (messy orders, duplicate invoices, blind payment matching) and gives a real, defensible "time saved / risk removed" number for the evaluation section: **€13,682 in unclear payments is the headline metric**, not a guess.

**Still needs a decision, not yet made:** picking one invoicing API (Billit vs Yuki vs others) and confirming it actually exposes what's needed — invoice creation, reverse-charge handling, and either built-in bank matching or a clean payment-confirmed webhook. If a trial account shows it *doesn't* cover bank matching well, add **Ponto** (Isabel Group, PSD2, supports KBC) as the bank-side piece instead of building that against the raw CSV export.

**Explicitly out of scope, folded in as a second workflow if time allows, not core:**
- Subscription lifecycle / auto-deactivation (123 stale active accounts) — same "trigger → decide → act" shape, but a separate data source (member DB), so a separate (smaller) workflow, not part of order-to-cash.
- Support ticket triage — real and quantified (497 tickets, 65 unanswered), but a genuinely different trigger and different risk profile (the phishing email is the reason this needs a human-approval step, not full autonomy). Good "week 11 with two more weeks" answer, not the core build.
- **Auto-captioning (Whisper or similar speech-to-text):** justified, not just possible — 0 of 599 videos have captions, confirmed in the Vimeo export, and it's directly tied to Pieter's own wish (ch.4: wanting to know which video shows which tool version without rewatching everything) since a searchable transcript solves that side-effect too. Shape: new video uploaded → trigger → transcribe → generate captions → push back via Vimeo's API. Worth separately checking whether EU accessibility rules actually apply to LoopCasts before treating this as a hard compliance deadline rather than a good-practice fix — flagging it, not asserting it.

**Separately — a one-line fix, not a workflow:** the 3 publicly-viewable paid videos found in the Vimeo export (`privacy=anybody`, no domain restriction) just need the privacy setting flipped back. No automation needed, just needs doing.

## What we deliberately do not touch (unchanged, still holds)

- **`login.php` / MySQL members backend** — SQL injection, hardcoded password, unsalted MD5 hashes, all real, but the handbook is explicit: *"Nobody here really understands it. We do not touch it,"* and there is no test site. Security remediation, not an automation task.
- **The shared password file / one-login-per-service setup** — a governance fix, not a workflow: move to **Bitwarden** (free tier covers a 5-person team), individual logins per person instead of one shared login per service.
- **The static site's file chaos and manual FTP deploys** — real debt, but the fix is version control and CI/CD (week 3–4 material), not part of this project.
- **Newsletter unsubscribe reconciliation** — real GDPR exposure (16 of 45 unsubscribe repliers, verified by matching addresses, are still on the 5,967-row list), small enough to fix directly rather than build a project around.

## Open questions for day one (in priority order)

1. **What does the red `account_created` flag actually mean** — done, or not done? 69% of 2026 orders are flagged. Checked `orders 2025.xlsx` too, since it's a closed, presumably fully-resolved year: **97% of it (685/707) is still flagged red.** That leans against "not yet done" as the meaning — a fully settled past year wouldn't plausibly have a 97% open backlog — but it's a lean, not a confirmation. Still don't design anything around this field until Lotte or Marieke says what it actually means.
2. Is the **€13,682 unconfirmed-payment number** something Marieke already suspects is that large, or does even she not know? (Directly testable against her own €4,000 estimate.)
3. The 6 reverse-charge VAT misses — does the accountant already know about the 5 uncorrected ones, or is this new information?
4. **32 support tickets asking for new courses or floating ideas** never made it to the whiteboard (per ch.5: *"They mostly do not"*) — is anyone even reviewing that inbox for product signal, or is it a dead end by design?
