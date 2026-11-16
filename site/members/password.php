<?php
declare(strict_types=1);
require __DIR__ . '/../lib/members.php';
require __DIR__ . '/../lib/layout.php';

$member = current_member();
if (!$member) {
    header('Location: /members/login.php');
    exit;
}

$error = null;
$done = false;
$key = 'change:' . $member['id'];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $current = (string)($_POST['current'] ?? '');
    $new = (string)($_POST['password'] ?? '');
    $again = (string)($_POST['password_again'] ?? '');

    if (!csrf_ok()) {
        http_response_code(400);
        $error = 'Your session expired. Please reload the page and try again.';
    } elseif (throttled($key)) {
        http_response_code(429);
        $error = 'Too many attempts. Wait 15 minutes and try again.';
    } else {
        $st = db()->prepare('SELECT password_hash FROM members WHERE id = :id');
        $st->execute([':id' => $member['id']]);
        $hash = (string)$st->fetchColumn();
        if (!password_verify($current, $hash)) {
            record_attempt($key);
            $error = 'Your current password is not right.';
        } elseif ($new === $current) {
            $error = 'Choose a password that is different from the current one.';
        } elseif ($new !== $again) {
            $error = 'The two passwords are not the same.';
        } elseif (($problem = password_error($new, $member['email'])) !== null) {
            $error = $problem;
        } else {
            db()->prepare('UPDATE members SET password_hash = :h WHERE id = :id')
                ->execute([':h' => password_hash($new, PASSWORD_DEFAULT), ':id' => $member['id']]);
            db()->prepare('UPDATE password_tokens SET used_at = NOW() WHERE member_id = :m AND used_at IS NULL')->execute([':m' => $member['id']]);
            clear_attempts($key);
            session_regenerate_id(true);
            $done = true;
        }
    }
}

page_start('Change your password', true);
?>
<h1 class="h1-small">Change your password</h1>
<?php if ($done): ?>
  <p class="notice">Your password was changed.</p>
  <p><a href="/members/">Back to your account</a></p>
<?php else: ?>
  <?php if ($error): ?><p class="notice notice-error" role="alert"><?= e($error) ?></p><?php endif; ?>
  <form class="form" method="post" action="/members/password.php">
    <?= csrf_field() ?>
    <div class="field"><label for="current">Current password</label>
      <input id="current" name="current" type="password" autocomplete="current-password"></div>
    <div class="field"><label for="password">New password</label>
      <input id="password" name="password" type="password" autocomplete="new-password">
      <p class="hint">At least 8 characters, with an uppercase letter, a lowercase letter, a digit and a special character.</p></div>
    <div class="field"><label for="password_again">Repeat the new password</label>
      <input id="password_again" name="password_again" type="password" autocomplete="new-password"></div>
    <div><button class="btn" type="submit">Change password</button></div>
  </form>
<?php endif; ?>
<?php page_end();