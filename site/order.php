<?php
declare(strict_types=1);

// Order page. A valid form creates a payment at the (simulated) provider and sends the customer to its checkout.
// The order itself is NOT created here: n8n creates it after the provider confirms the payment.
require __DIR__ . '/lib/bootstrap.php';
require __DIR__ . '/lib/shop.php';
require __DIR__ . '/lib/payments.php';

$plans = PLANS;
$courses = COURSES;
$countries = COUNTRIES;

$planKey = (string)($_POST['plan'] ?? $_GET['plan'] ?? 'yearly');
if (!isset($plans[$planKey])) { $planKey = 'yearly'; }
$plan = $plans[$planKey];

$v = ['name' => '', 'email' => '', 'is_company' => '', 'company' => '', 'vat' => '', 'country' => 'BE', 'course' => ''];
$errors = [];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    foreach ($v as $k => $_) { $v[$k] = trim((string)($_POST[$k] ?? '')); }

    if ($v['name'] === '') { $errors['name'] = 'Enter your name.'; }
    if (!filter_var($v['email'], FILTER_VALIDATE_EMAIL)) { $errors['email'] = 'Enter a valid email address.'; }
    if (!isset($countries[$v['country']])) { $errors['country'] = 'Choose a country.'; }
    if ($planKey === 'single' && !in_array($v['course'], $courses, true)) { $errors['course'] = 'Choose a course.'; }

    if ($v['is_company'] === '1') {
        if ($v['company'] === '') { $errors['company'] = 'Enter the company name.'; }
        $vat = strtoupper((string)preg_replace('/[\s.\-]/', '', $v['vat']));
        if ($vat === '') {
            $errors['vat'] = 'Enter the VAT number, for example BE0123456789.';
        } elseif (!preg_match('/^[A-Z]{2}[A-Z0-9]{8,12}$/', $vat)) {
            $errors['vat'] = 'This does not look like a VAT number. Start with the country code, for example BE0123456789.';
        } else {
            $v['vat'] = $vat;
        }
    }

    if ($errors === []) {
        $isCompany = $v['is_company'] === '1';
        $rule = vat_rule($v['country'], $isCompany, $isCompany ? $v['vat'] : '');
        $excl = $plan['cents'];
        $vatCents = vat_cents($excl, $rule);
        $description = $plan['name'] . ($planKey === 'single' ? ': ' . $v['course'] : '');
        $id = create_payment($excl + $vatCents, $description, [
            'plan' => $planKey,
            'course' => $planKey === 'single' ? $v['course'] : null,
            'name' => $v['name'],
            'email' => $v['email'],
            'company' => $isCompany ? $v['company'] : null,
            'vat_number' => $isCompany ? $v['vat'] : null,
            'country' => $v['country'],
            'amount_excl_cents' => $excl,
            'vat_cents' => $vatCents,
            'vat_rule' => $rule,
        ]);
        header('Location: /pay/checkout.php?id=' . $id);
        exit;
    }
}

function field_attrs(array $errors, string $key): string {
    return isset($errors[$key]) ? ' aria-invalid="true" aria-describedby="err-' . $key . '"' : '';
}
function field_error(array $errors, string $key): string {
    return isset($errors[$key]) ? '<p class="field-error" id="err-' . $key . '">' . e($errors[$key]) . '</p>' : '';
}
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Order <?= e($plan['name']) ?>: LoopCasts</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <a class="skip" href="#main">Skip to content</a>
  <header class="bar">
    <div class="wrap bar-inner">
      <a class="brand" href="index.html">LoopCasts</a>
      <nav aria-label="Main">
        <a href="index.html#courses">Courses</a>
        <a href="index.html#pricing">Pricing</a>
      </nav>
    </div>
  </header>

  <main id="main" class="wrap narrow section">
    <h1 class="h1-small">Order: <?= e($plan['name']) ?></h1>
    <p class="sub"><?= e($plan['price']) ?>, excluding VAT. <?= e($plan['note']) ?></p>

<?php if ($errors): ?>
    <p class="notice" role="alert">Check the <?= count($errors) === 1 ? 'highlighted field' : count($errors) . ' highlighted fields' ?> and try again.</p>
<?php endif; ?>

    <form class="form" method="post" action="order.php" novalidate>
      <input type="hidden" name="plan" value="<?= e($planKey) ?>">

      <div class="field">
        <label for="name">Your name</label>
        <input id="name" name="name" type="text" autocomplete="name" value="<?= e($v['name']) ?>"<?= field_attrs($errors, 'name') ?>>
        <?= field_error($errors, 'name') ?>
      </div>

      <div class="field">
        <label for="email">Email address</label>
        <input id="email" name="email" type="email" autocomplete="email" value="<?= e($v['email']) ?>"<?= field_attrs($errors, 'email') ?>>
        <p class="hint">We send your invoice and login here.</p>
        <?= field_error($errors, 'email') ?>
      </div>

<?php if ($planKey === 'single'): ?>
      <div class="field">
        <label for="course">Course</label>
        <select id="course" name="course"<?= field_attrs($errors, 'course') ?>>
          <option value="">Choose a course</option>
<?php foreach ($courses as $c): ?>
          <option<?= $v['course'] === $c ? ' selected' : '' ?>><?= e($c) ?></option>
<?php endforeach; ?>
        </select>
        <?= field_error($errors, 'course') ?>
      </div>
<?php endif; ?>

      <div class="check">
        <input id="is_company" name="is_company" type="checkbox" value="1"<?= $v['is_company'] === '1' ? ' checked' : '' ?>>
        <label for="is_company">I am ordering for a company</label>
      </div>

      <div id="company-fields" class="form">
        <div class="field">
          <label for="company">Company name</label>
          <input id="company" name="company" type="text" autocomplete="organization" value="<?= e($v['company']) ?>"<?= field_attrs($errors, 'company') ?>>
          <?= field_error($errors, 'company') ?>
        </div>
        <div class="field">
          <label for="vat">VAT number</label>
          <input id="vat" name="vat" type="text" value="<?= e($v['vat']) ?>"<?= field_attrs($errors, 'vat') ?>>
          <p class="hint">Companies in another EU country with a valid VAT number pay no Belgian VAT.</p>
          <?= field_error($errors, 'vat') ?>
        </div>
      </div>

      <div class="field">
        <label for="country">Country</label>
        <select id="country" name="country"<?= field_attrs($errors, 'country') ?>>
<?php foreach ($countries as $code => $label): ?>
          <option value="<?= e($code) ?>"<?= $v['country'] === $code ? ' selected' : '' ?>><?= e($label) ?></option>
<?php endforeach; ?>
        </select>
        <?= field_error($errors, 'country') ?>
      </div>

      <div><button class="btn" type="submit">Continue</button></div>
    </form>

    <script>
      // Company fields only show when the box is ticked. Without JavaScript they stay visible.
      (function () {
        var box = document.getElementById('is_company');
        var fields = document.getElementById('company-fields');
        function sync() { fields.hidden = !box.checked; }
        box.addEventListener('change', sync);
        sync();
      })();
    </script>
  </main>

  <footer class="foot">
    <div class="wrap">
      <p><strong>LoopCasts BV</strong></p>
      <p>Fietsstraat 12 bus 2, 9000 Gent</p>
      <p class="fine">&copy; 2026 LoopCasts BV</p>
    </div>
  </footer>
</body>
</html>