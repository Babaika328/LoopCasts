<?php
declare(strict_types=1);
require __DIR__ . '/../lib/members.php';
require __DIR__ . '/../lib/layout.php';
require_once __DIR__ . '/../lib/shop.php';

$member = current_member();
if (!$member) {
    header('Location: /members/login.php');
    exit;
}

$st = db()->prepare('SELECT o.plan, o.course, o.created_at, i.invoice_number FROM orders o LEFT JOIN invoices i ON i.order_id = o.id WHERE o.email = :e ORDER BY o.id DESC');
$st->execute([':e' => $member['email']]);
$orders = $st->fetchAll();

// "Renew" goes to the order page with the plan the member bought last (a single course renews as a yearly plan).
$last = $orders[0]['plan'] ?? 'yearly';
$renewPlan = in_array($last, ['monthly', 'yearly', 'team'], true) ? $last : 'yearly';
$endsSoon = $member['access_until'] !== null && (int)$member['days_left'] <= 30;

page_start('Your account', true);
?>
<h1 class="h1-small">Hello, <?= e($member['name']) ?></h1>
<?php if ($member['access_until'] === null): ?>
  <p class="notice">You have no active subscription.</p>
<?php elseif ((int)$member['active'] === 1): ?>
  <p class="notice">Your subscription is active until <?= e(date('d/m/Y', strtotime($member['access_until']))) ?>.</p>
<?php else: ?>
  <p class="notice notice-error" role="alert">Your subscription ended on <?= e(date('d/m/Y', strtotime($member['access_until']))) ?>.</p>
<?php endif; ?>
<?php if ($endsSoon): ?>
  <p><a class="btn" href="/order.php?plan=<?= e($renewPlan) ?>">Renew your subscription</a></p>
<?php endif; ?>

<h2>Your orders</h2>
<?php if (!$orders): ?><p>No orders yet.</p><?php else: ?>
<ul class="courses">
<?php foreach ($orders as $o): ?>
  <li><span class="c-title"><?= e(PLAN_NAMES[$o['plan']] ?? $o['plan']) ?><?= $o['course'] ? ': ' . e($o['course']) : '' ?></span>
      <span><?= e(date('d/m/Y', strtotime($o['created_at']))) ?></span>
      <span><?php if ($o['invoice_number']): ?><a href="/members/invoice.php?n=<?= e($o['invoice_number']) ?>">Invoice <?= e($o['invoice_number']) ?></a><?php endif; ?></span></li>
<?php endforeach; ?>
</ul>
<?php endif; ?>

<p class="stack-top"><a href="/members/profile.php">Your details and privacy</a></p>
<p><a href="/members/password.php">Change your password</a></p>
<form method="post" action="/members/logout.php" class="stack-top">
  <?= csrf_field() ?>
  <button class="btn btn-quiet" type="submit">Log out</button>
</form>
<?php page_end();