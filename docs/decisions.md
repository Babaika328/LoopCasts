# Why each part exists

Rule used all through the project: if we cannot say which problem a part removes, with evidence, it does not belong.
Some things were left as they are on purpose, and that is stated here too. Numbers come from the handbook and from the
files; ticket shares are counted from subject lines, which are often wrong (about 6 of 20 sampled emails had a misleading
subject), so treat them as rough.

## 1. Automated, and why this is the right kind of task
Each one has the same shape: a trigger, data, a rule, an action, and a lot of repetition.

| Part | Problem seen | What happens now | Why not something else |
|---|---|---|---|
| Order form and online payment | Orders arrive as free text by mail (about 1 in 3 incomplete), retyped into Excel in 5 to 15 minutes, about 35 a week | A form with required fields, then a hosted checkout | A rule-based task: no AI needed. An AI parser for the mails was dropped once checkout existed |
| Payment confirmation | Payments matched by eye on Fridays; only 19% of bank payments carry a usable reference | The provider's webhook carries only a payment id, n8n asks the provider for the real status | The webhook alone cannot be trusted, asking the provider is the check |
| Invoice number | The same number went out twice (2026-0071), gaps at 0023, 0088 and 0241 | The database hands out the next number inside one transaction | Tested with 12 simultaneous requests, 80 rounds, no duplicate. A person cannot guarantee that |
| VAT rule and amount check | 4 reverse-charge errors still uncorrected out of 38 foreign business orders | The rule is code, and a second independent calculation must agree with what was paid or the run stops | The rule is exact, so code is better than memory |
| Invoice email | One day a month copying Word files for about 210 monthly invoices | The invoice is built and sent once per order | Dedupe by an owner number, so a repeated webhook sends one email |
| Access after payment | Accounts typed by hand in phpMyAdmin (5 minutes), passwords mailed in plain text | The site creates the account and mails a one-time link to choose a password | About 9% of tickets are "paid but no login" |
| Password reset | About 23% of tickets, and the old process did not check who was asking | A one-time link, valid 2 hours, only a hash stored | A standard mechanism, no human step |
| Ended subscriptions still working (123) | Switching them off was the step that slipped | The end date is checked on every visit | No scheduled job is needed. This one is solved by design |
| Alerts, tests, backup check | Failures were silent, backups never restored | Error workflow mails a human, 120+ automatic tests, a backup that proves it can be restored | "Nothing fails silently" |
| Support triage with AI | 497 tickets, 21.8 hours to a first answer, 65 never answered | AI classifies and drafts, a person approves in the admin panel | Free text in two languages, subjects often wrong: keyword rules are not enough. The AI never sends |

## 2. Built, but not an automation
The members area, profile and admin panel are screens, not workflows. They exist because moving from Excel to a database
would otherwise leave staff with nothing but phpMyAdmin. They replace the colour-coded sheets, give the AI an approval
step, and keep a record of who did what.

## 3. Left as it is, on purpose
- **Cancellations and refunds.** The handbook says Marieke decides. A request is routed to a person, never decided by a program. About 5% of tickets.
- **Team seats** (about 7% of tickets). Stays as a ticket with an AI draft. A full seat manager is a big feature for a small share.
- **Invoices as PDF.** The invoice is shown as a printable page. A real company would buy an invoicing service that also sends Peppol invoices; we cannot open a live account for a case company.
- **The 54 hand-copied course pages.** A real pain for Tom, but outside the order-to-cash chain. Roadmap.
- **Caption generation for the videos** and **renewal reminders.** Reasonable, cheap to add later; the reminder is the first to build if time allows.
- **The old Excel files.** Kept as an archive, not migrated. The 1,961 old accounts have MD5 passwords and need their own migration plan.
- **The real payment provider.** Simulated, following the documented behaviour, because a case company cannot have a live account.
- **AI sending replies on its own.** Never. A person approves every reply.
