<?php
declare(strict_types=1);
require __DIR__ . '/../lib/members.php';
require __DIR__ . '/../lib/layout.php';

start_session();
$sent = false;
$error = null;
$email = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $email = strtolower(trim((string)($_POST['email'] ?? '')));
    $key = 'forgot:' . $email;
    if (!csrf_ok()) {
        http_response_code(400);
        $error = 'Your session expired. Please try again.';
    } elseif (throttled($key)) {
        http_response_code(429);
        $error = 'Too many requests. Wait 15 minutes and try again.';
    } else {
        record_attempt($key);
        if (filter_var($email, FILTER_VALIDATE_EMAIL)) {
            $st = db()->prepare('SELECT id FROM members WHERE email = :e');
            $st->execute([':e' => $email]);
            $memberId = $st->fetchColumn();
            if ($memberId) {
                $token = new_token((int)$memberId, 'reset');
                send_mail($email, 'Reset your LoopCasts password',
                    "Hello,\n\nSomeone asked to reset the password of this LoopCasts account.\n"
                    . "If it was you, choose a new password here (the link works for 2 hours, once):\n\n"
                    . site_url() . '/members/set-password.php?token=' . $token . "\n\n"
                    . "If it was not you, ignore this email: nothing changes.\n\nLoopCasts support\n");
            }
        }
        $sent = true;   // the same answer whether the address is a member or not
    }
}

page_start('Forgot your password');
?>
<h1 class="h1-small">Forgot your password?</h1>
<?php if ($sent): ?>
  <p class="notice">If this address belongs to a member, we have sent a link to choose a new password. It works for 2 hours.</p>
  <p><a href="/members/login.php">Back to log in</a></p>
<?php else: ?>
  <?php if ($error): ?><p class="notice notice-error" role="alert"><?= e($error) ?></p><?php endif; ?>
  <form class="form" method="post" action="/members/forgot.php">
    <?= csrf_field() ?>
    <div class="field"><label for="email">Email address</label>
      <input id="email" name="email" type="email" autocomplete="username" value="<?= e($email) ?>"></div>
    <div><button class="btn" type="submit">Send me a link</button></div>
  </form>
<?php endif; ?>
<?php page_end();