<?php
declare(strict_types=1);
require __DIR__ . '/lib/bootstrap.php';
require __DIR__ . '/lib/payments.php';

$p = find_payment((string)($_GET['id'] ?? ''));
if ($p === null) { http_response_code(404); }
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Your order: LoopCasts</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header class="bar">
    <div class="wrap bar-inner">
      <a class="brand" href="index.html">LoopCasts</a>
      <nav aria-label="Main"><a href="index.html#courses">Courses</a><a href="index.html#pricing">Pricing</a></nav>
    </div>
  </header>
  <main class="wrap narrow section">
<?php if ($p === null): ?>
    <h1 class="h1-small">We could not find this order</h1>
    <p><a href="index.html#pricing">Back to the plans</a></p>
<?php elseif ($p['status'] === 'paid'): ?>
    <h1 class="h1-small">Thank you, your payment was received</h1>
    <p><?= e($p['description']) ?>, <?= e(euro((int)$p['amount_cents'])) ?> including VAT.</p>
    <p class="notice">Development version: invoice and login emails are connected in a later step.</p>
<?php elseif ($p['status'] === 'open'): ?>
    <h1 class="h1-small">Your payment is not finished</h1>
    <p><a href="/pay/checkout.php?id=<?= e($p['id']) ?>">Continue to payment</a></p>
<?php else: ?>
    <h1 class="h1-small">The payment did not go through</h1>
    <p>Nothing was charged. You can <a href="index.html#pricing">choose a plan and try again</a>.</p>
<?php endif; ?>
  </main>
</body>
</html>
