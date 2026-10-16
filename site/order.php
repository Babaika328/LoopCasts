<?php
declare(strict_types=1);

// Order page. For now it only checks the details; payment is connected in the next step.

$plans = [
    'monthly' => ['name' => 'Monthly',       'price' => '€15 per month', 'note' => 'Access to everything. Billed every month.'],
    'yearly'  => ['name' => 'Yearly',        'price' => '€149 per year', 'note' => 'Access to everything.'],
    'team'    => ['name' => 'Team licence',  'price' => '€599 per year', 'note' => 'Five seats. After payment you send us the five names.'],
    'single'  => ['name' => 'Single course', 'price' => '€39',           'note' => 'Lifetime access to one course.'],
];
$courses = [
    'n8n basics', 'Webhooks from zero', 'REST APIs for data people',
    'Shell scripting that saves your week', 'Cron and schedulers', 'GitHub Actions in practice',
];
$countries = [
    'BE' => 'Belgium', 'NL' => 'Netherlands', 'FR' => 'France', 'DE' => 'Germany',
    'LU' => 'Luxembourg', 'IT' => 'Italy', 'ES' => 'Spain', 'IE' => 'Ireland',
];

function e(string $s): string { return htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }

$planKey = (string)($_POST['plan'] ?? $_GET['plan'] ?? 'yearly');
if (!isset($plans[$planKey])) { $planKey = 'yearly'; }
$plan = $plans[$planKey];

$v = ['name' => '', 'email' => '', 'is_company' => '', 'company' => '', 'vat' => '', 'country' => 'BE', 'course' => ''];
$errors = [];
$done = false;

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
    $done = $errors === [];
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
<?php if ($done): ?>
    <h1 class="h1-small">Your details look good</h1>
    <div class="summary">
      <h2><?= e($plan['name']) ?>, <?= e($plan['price']) ?></h2>
      <dl class="facts">
        <dt>Name</dt><dd><?= e($v['name']) ?></dd>
        <dt>Email</dt><dd><?= e($v['email']) ?></dd>
        <?php if ($v['is_company'] === '1'): ?>
        <dt>Company</dt><dd><?= e($v['company']) ?></dd>
        <dt>VAT number</dt><dd><?= e($v['vat']) ?></dd>
        <?php endif; ?>
        <dt>Country</dt><dd><?= e($countries[$v['country']]) ?></dd>
        <?php if ($planKey === 'single'): ?>
        <dt>Course</dt><dd><?= e($v['course']) ?></dd>
        <?php endif; ?>
      </dl>
    </div>
    <p class="notice">Development version: nothing has been saved and no payment was taken. The payment step is connected next.</p>
    <p><a href="index.html#pricing">Back to the plans</a></p>
<?php else: ?>
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
<?php endif; ?>
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