// n8n Code node "Validate triage" (mode: Run Once for All Items).
// The model's answer is never trusted as it is: it is parsed and checked, and on any doubt the email goes to a human.
// Input: the language model node's "text" output, and the original email from the node "Support webhook".
const CATEGORIES = ['login_access', 'invoice_request', 'order_status', 'content_question', 'video_problem', 'team_seats',
  'cancel_or_refund', 'idea_or_partnership', 'scam_or_spam', 'other'];
const ALWAYS_HUMAN = ['cancel_or_refund', 'scam_or_spam', 'other'];
const ALLOWED_PLACEHOLDERS = ['{{INVOICE_NUMBER}}', '{{ORDER_STATUS}}'];
const PROMISES = /refund|terugbetal|rembours|korting|discount|gratis|free access|kostenlos/i;

const email = $('Support webhook').first().json.body;
const raw = String($input.first().json.text ?? $input.first().json.output ?? '');

function failSafe(reason) {
  return [{ json: { ...email, category: 'other', language: 'other', needs_human: true, confidence: 0, draft_reply: '', validation_note: reason } }];
}

let a;
try {
  a = JSON.parse(raw.trim().replace(/^```(?:json)?/i, '').replace(/```$/, '').trim());
} catch (e) {
  return failSafe('The model did not return valid JSON');
}

if (!CATEGORIES.includes(a.category)) return failSafe('Unknown category: ' + a.category);
if (typeof a.needs_human !== 'boolean') return failSafe('needs_human is not true or false');
if (typeof a.confidence !== 'number' || a.confidence < 0 || a.confidence > 1) return failSafe('confidence is not a number from 0 to 1');
if (typeof a.draft_reply !== 'string') return failSafe('draft_reply is not text');

let needsHuman = a.needs_human;
let draft = a.draft_reply.trim();
const notes = [];

if (ALWAYS_HUMAN.includes(a.category)) { needsHuman = true; notes.push('policy: this category always goes to a human'); }
if (a.confidence < 0.6) { needsHuman = true; notes.push('low confidence'); }
if (draft.length > 1200) { needsHuman = true; notes.push('draft too long'); }
if (/https?:\/\/|www\./i.test(draft)) { needsHuman = true; notes.push('draft contains a link'); }
if (PROMISES.test(draft)) { needsHuman = true; notes.push('draft promises something'); }
const placeholders = draft.match(/\{\{[A-Z_]+\}\}/g) || [];
if (placeholders.some((p) => !ALLOWED_PLACEHOLDERS.includes(p))) { needsHuman = true; notes.push('draft uses an unknown placeholder'); }
if (needsHuman) draft = '';

return [{ json: { ...email, category: a.category, language: a.language ?? 'other', needs_human: needsHuman,
  confidence: a.confidence, draft_reply: draft, validation_note: notes.join('; ') } }];