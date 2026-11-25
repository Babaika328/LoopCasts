<?php
declare(strict_types=1);
require __DIR__ . '/../lib/members.php';
require __DIR__ . '/../lib/layout.php';
require __DIR__ . '/../lib/invoice.php';

$member = current_member();
if (!$member) {
    header('Location: /members/login.php');
    exit;
}
$number = (string)($_GET['n'] ?? '');
$row = preg_match('/^\d{4}-\d{4}$/', $number) ? find_invoice_for($number, $member['email']) : null;
if (!$row) {
    http_response_code(404);   // the same answer for "does not exist" and "belongs to someone else"
    page_start('Invoice not found', true);
    echo '<h1 class="h1-small">Invoice not found</h1><p><a href="/members/">Back to your account</a></p>';
    page_end();
    exit;
}
page_start('Invoice ' . $number, true);
echo render_invoice($row);
echo '<p class="no-print actions"><a class="btn" href="#" id="print-invoice">Print or save as PDF</a> <a class="btn btn-quiet" href="/members/">Back to your account</a></p>';
echo '<script src="/print.js"></script>';
page_end();