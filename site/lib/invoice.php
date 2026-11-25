<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';

function eur_be(int $cents): string
{
    return '€ ' . number_format($cents / 100, 2, ',', '');
}

// An invoice, but only for the member it belongs to (matched on the order's email). Anything else is "not found".
function find_invoice_for(string $number, string $email): ?array
{
    $st = db()->prepare('SELECT i.invoice_number, i.issued_on, i.total_cents, o.plan, o.course, o.name, o.email, o.company, o.vat_number,
                                o.country, o.amount_excl_cents, o.vat_cents, o.vat_rule
                         FROM invoices i JOIN orders o ON o.id = i.order_id WHERE i.invoice_number = :n AND o.email = :e');
    $st->execute([':n' => $number, ':e' => $email]);
    return $st->fetch() ?: null;
}

// The invoice as an HTML fragment. Everything that came from a customer is escaped.
function render_invoice(array $r): string
{
    $lines = ['monthly' => 'Monthly subscription LoopCasts', 'yearly' => 'Yearly subscription LoopCasts',
              'team' => 'Team licence LoopCasts (5 seats)', 'single' => 'Single course: ' . ($r['course'] ?? '')];
    $reverse = $r['vat_rule'] === 'reverse_charge';
    $to = e($r['company'] ?: $r['name']) . '<br>' . ($r['company'] ? e($r['name']) . '<br>' : '')
        . ($r['vat_number'] ? 'VAT ' . e($r['vat_number']) . '<br>' : '') . e($r['email']);
    return '<article class="invoice">'
        . '<p class="invoice-seller"><strong>LoopCasts BV</strong><br>Fietsstraat 12 bus 2, 9000 Gent<br>VAT BE 0712.345.678</p>'
        . '<h1 class="h1-small invoice-title">Invoice ' . e($r['invoice_number']) . '</h1>'
        . '<p class="sub">Date: ' . e(date('d/m/Y', strtotime($r['issued_on']))) . '</p>'
        . '<p class="invoice-to"><strong>To</strong><br>' . $to . '</p>'
        . '<table class="invoice-table"><thead><tr><th scope="col">Description</th><th scope="col" class="num">Amount (EUR)</th></tr></thead><tbody>'
        . '<tr><td>' . e($lines[$r['plan']] ?? 'LoopCasts') . '</td><td class="num">' . e(eur_be((int)$r['amount_excl_cents'])) . '</td></tr>'
        . '<tr><td>' . ($reverse ? 'VAT 0% (VAT reverse charged)' : 'VAT 21%') . '</td><td class="num">' . e(eur_be((int)$r['vat_cents'])) . '</td></tr>'
        . '<tr class="total"><td>Total</td><td class="num">' . e(eur_be((int)$r['total_cents'])) . '</td></tr></tbody></table>'
        . '<p>Paid online. Thank you for learning with LoopCasts!</p></article>';
}