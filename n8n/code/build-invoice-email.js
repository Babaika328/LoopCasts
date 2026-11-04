// n8n Code node "Build invoice email" (mode: Run Once for All Items).
// Reads the nodes "Get order" and "Get invoice" and returns { to, subject, html } for the Send Email node.
// The workflow JSON is the source of truth; this copy is here so the code can be read, reviewed and tested.
const order = $('Get order').first().json;
const inv = $('Get invoice').first().json;

// Everything that came from a customer is escaped, so it can never inject HTML into the email.
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
const eur = (cents) => '€ ' + (Number(cents) / 100).toFixed(2).replace('.', ',');
const day = (d) => new Date(d).toLocaleDateString('en-GB', { timeZone: 'Europe/Brussels' });

const names = {
  monthly: 'Monthly subscription LoopCasts',
  yearly: 'Yearly subscription LoopCasts',
  team: 'Team licence LoopCasts (5 seats)',
  single: 'Single course: ' + (order.course || ''),
};
const description = names[order.plan] || 'LoopCasts';
const reverse = order.vat_rule === 'reverse_charge';
const total = Number(inv.total_cents);

// Never send an invoice whose lines do not add up to its total.
if (Number(order.amount_excl_cents) + Number(order.vat_cents) !== total) {
  throw new Error(`Invoice ${inv.invoice_number}: lines (${order.amount_excl_cents} + ${order.vat_cents}) do not add up to the total ${total}`);
}

const row = (label, value, bold) =>
  `<tr><td style="padding:10px 0;border-top:1px solid #cfe8dc;${bold ? 'font-weight:bold;' : ''}">${label}</td>` +
  `<td align="right" style="padding:10px 0;border-top:1px solid #cfe8dc;${bold ? 'font-weight:bold;' : ''}">${value}</td></tr>`;

const html = `<!doctype html>
<html><body style="margin:0;background:#eaf7f1;font-family:Arial,Helvetica,sans-serif;color:#17332a;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eaf7f1;padding:24px 12px;"><tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;background:#ffffff;border-radius:12px;">
  <tr><td style="padding:28px 32px 8px;">
    <div style="font-size:22px;font-weight:bold;">LoopCasts</div>
    <div style="font-size:13px;line-height:1.5;color:#4a6b5e;margin-top:4px;">LoopCasts BV, Fietsstraat 12 bus 2, 9000 Gent<br>VAT BE 0712.345.678</div>
  </td></tr>
  <tr><td style="padding:16px 32px;">
    <div style="font-size:28px;font-weight:bold;color:#1f7a5c;">Invoice ${esc(inv.invoice_number)}</div>
    <div style="font-size:14px;color:#4a6b5e;margin-top:4px;">Date: ${esc(day(inv.issued_on))}</div>
  </td></tr>
  <tr><td style="padding:8px 32px 20px;font-size:14px;line-height:1.6;">
    <strong>To</strong><br>${esc(order.company || order.name)}<br>${order.company ? esc(order.name) + '<br>' : ''}${order.vat_number ? 'VAT ' + esc(order.vat_number) + '<br>' : ''}${esc(order.email)}
  </td></tr>
  <tr><td style="padding:0 32px 8px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:14px;">
      <tr><td style="padding:8px 0;color:#4a6b5e;font-size:12px;">Description</td><td align="right" style="padding:8px 0;color:#4a6b5e;font-size:12px;">Amount (EUR)</td></tr>
      ${row(esc(description), eur(order.amount_excl_cents))}
      ${row(reverse ? 'VAT 0% (VAT reverse charged)' : 'VAT 21%', eur(order.vat_cents))}
      ${row('Total', eur(total), true)}
    </table>
  </td></tr>
  <tr><td style="padding:16px 32px 28px;font-size:14px;line-height:1.6;">
    Paid online. Thank you for learning with LoopCasts!
  </td></tr>
</table>
</td></tr></table>
</body></html>`;

return [{ json: { to: order.email, subject: `Your LoopCasts invoice ${inv.invoice_number}`, html } }];