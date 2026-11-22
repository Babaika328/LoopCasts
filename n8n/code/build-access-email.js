// n8n Code node "Build access email" (mode: Run Once for All Items).
// Input: the answer of the node "Grant access" (the members API of the site).
// Returns { to, subject, html } for the Send Email node. The link comes from our own site and is only shown once:
// it is never stored in plain text, so if this email is lost the customer uses "Forgot your password?".
const a = $input.first().json;

const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
const day = (d) => new Date(d).toLocaleDateString('en-GB', { timeZone: 'Europe/Brussels' });

// Never send a broken or foreign link.
if (!/^https?:\/\/[^\s"'<>]+\/members\/set-password\.php\?token=[0-9a-f]{64}$/.test(String(a.setup_url ?? ''))) {
  throw new Error('The members API did not return a valid password link');
}

const until = a.access_until
  ? `<p style="margin:0 0 16px;">Your subscription is active until <strong>${esc(day(a.access_until))}</strong>.</p>`
  : '<p style="margin:0 0 16px;">Your course is ready for you.</p>';

const html = `<!doctype html>
<html><body style="margin:0;background:#eaf7f1;font-family:Arial,Helvetica,sans-serif;color:#17332a;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eaf7f1;padding:24px 12px;"><tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;background:#ffffff;border-radius:12px;">
  <tr><td style="padding:28px 32px 8px;font-size:22px;font-weight:bold;">LoopCasts</td></tr>
  <tr><td style="padding:8px 32px 0;">
    <div style="font-size:26px;font-weight:bold;color:#1f7a5c;">Welcome, ${esc(a.name)}</div>
  </td></tr>
  <tr><td style="padding:16px 32px 8px;font-size:14px;line-height:1.6;">
    <p style="margin:0 0 16px;">Thank you for your order. Your account is ready: choose a password and you can log in.</p>
    ${until}
    <p style="margin:24px 0;"><a href="${esc(a.setup_url)}" style="display:inline-block;background:#1f7a5c;color:#ffffff;text-decoration:none;font-weight:bold;padding:14px 24px;border-radius:10px;">Choose your password</a></p>
    <p style="margin:0 0 8px;color:#4a6b5e;font-size:13px;">The link works for 7 days and only once. If it has expired, use &ldquo;Forgot your password?&rdquo; on the login page.</p>
    <p style="margin:0 0 24px;color:#4a6b5e;font-size:13px;">We will never ask for your password by email.</p>
  </td></tr>
</table>
</td></tr></table>
</body></html>`;

return [{ json: { to: a.email, subject: 'Welcome to LoopCasts: choose your password', html } }];