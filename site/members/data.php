<?php
declare(strict_types=1);
require __DIR__ . '/../lib/members.php';
require __DIR__ . '/../lib/audit.php';

// "Download my data": everything we hold about the logged-in member, as a file. Never includes the password hash.
$member = current_member();
if (!$member) {
    header('Location: /members/login.php');
    exit;
}
$st = db()->prepare('SELECT name, email, created_at, last_login_at, access_until FROM members WHERE id = :id');
$st->execute([':id' => $member['id']]);
$profile = $st->fetch();

$st = db()->prepare('SELECT o.created_at, o.plan, o.course, o.amount_excl_cents, o.vat_cents, o.vat_rule, o.status, i.invoice_number, i.issued_on
                     FROM orders o LEFT JOIN invoices i ON i.order_id = o.id WHERE o.email = :e ORDER BY o.id');
$st->execute([':e' => $member['email']]);
$orders = $st->fetchAll();

$st = db()->prepare('SELECT received_at, source, subject, category, status FROM tickets WHERE member_id = :m OR from_email = :e ORDER BY id');
$st->execute([':m' => $member['id'], ':e' => $member['email']]);
$tickets = $st->fetchAll();

audit('data_export', 'member:' . $member['id']);
header('Content-Type: application/json; charset=utf-8');
header('Content-Disposition: attachment; filename="loopcasts-my-data.json"');
header('Cache-Control: no-store');
echo json_encode(['exported_at' => date('c'), 'profile' => $profile, 'orders' => $orders, 'requests_and_tickets' => $tickets],
    JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);