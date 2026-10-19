<?php
declare(strict_types=1);
// Test checkout page (stands in for the provider's hosted checkout). Nothing is ever charged.
require __DIR__ . '/../lib/bootstrap.php';
require __DIR__ . '/../lib/payments.php';

$id = (string)($_GET['id'] ?? $_POST['id'] ?? '');
$p = find_payment($id);
if ($p === null) { http_response_code(404); exit('Unknown payment.'); }

$result = null;     // set after the customer pressed a button
if ($_SERVER['REQUEST_METHOD'] === 'POST' && $p['status'] === 'open') {
    $map = ['pay' => 'paid', 'fail' => 'failed', 'cancel' => 'canceled'];
    $action = (string)($_POST['action'] ?? '');
    if (isset($map[$action])) {
        $st = db()->prepare('UPDATE payments SET status = :s, paid_at = IF(:s2 = "paid", NOW(), NULL) WHERE id = :id AND status = "open"');
        $st->execute([':s' => $map[$action], ':s2' => $map[$action], ':id' => $id]);
        $times = !empty($_POST['twice']) ? 2 : 1;      // test option: deliver the webhook twice
        $result = [];
        for ($i = 0; $i < $times; $i++) { $result[] = send_webhook($p['webhook_url'], $id); }
        $p = find_payment($id);
    }
}
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Test checkout</title>
  <link rel="stylesheet" href="/style.css">
</head>
<body>
  <main class="wrap narrow section">
    <p class="notice"><strong>Test checkout.</strong> This simulates a payment provider. Nothing is charged.</p>
    <h1 class="h1-small"><?= e($p['description']) ?></h1>
    <p class="price"><?= e(euro((int)$p['amount_cents'])) ?> <span>including VAT</span></p>

<?php if ($result !== null): ?>
    <div class="summary">
      <h2>Payment <?= e($p['status']) ?></h2>
      <p>Webhook delivery: <?= e(implode(', ', $result)) ?></p>
      <p><a class="btn" href="<?= e($p['redirect_url']) ?>">Back to the shop</a></p>
    </div>
<?php elseif ($p['status'] !== 'open'): ?>
    <p>This payment is already <strong><?= e($p['status']) ?></strong>.</p>
    <p><a href="<?= e($p['redirect_url']) ?>">Back to the shop</a></p>
<?php else: ?>
    <form class="form" method="post" action="/pay/checkout.php">
      <input type="hidden" name="id" value="<?= e($id) ?>">
      <div class="check">
        <input id="twice" name="twice" type="checkbox" value="1">
        <label for="twice">Test option: send the webhook twice</label>
      </div>
      <div class="actions">
        <button class="btn" type="submit" name="action" value="pay">Pay</button>
        <button class="btn btn-quiet" type="submit" name="action" value="fail">Payment fails</button>
        <button class="btn btn-quiet" type="submit" name="action" value="cancel">Cancel</button>
      </div>
    </form>
<?php endif; ?>
  </main>
</body>
</html>
