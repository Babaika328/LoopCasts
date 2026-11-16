<?php
declare(strict_types=1);
require __DIR__ . '/../lib/members.php';
require __DIR__ . '/../lib/layout.php';

start_session();
$token = (string)($_POST['token'] ?? $_GET['token'] ?? '');
$info = find_valid_token($token);
$error = null;

if ($info && $_SERVER['REQUEST_METHOD'] === 'POST') {
    $password = (string)($_POST['password'] ?? '');
    $again = (string)($_POST['password_again'] ?? '');
    if (!csrf_ok()) {
        http_response_code(400);
        $error = 'Your session expired. Please reload the page and try again.';
    } elseif ($password !== $again) {
        $error = 'The two passwords are not the same.';
    } elseif (($problem = password_error($password, $info['email'])) !== null) {
        $error = $problem;
    } else {
        db()->prepare('UPDATE members SET password_hash = :h WHERE id = :id')
            ->execute([':h' => password_hash($password, PASSWORD_DEFAULT), ':id' => $info['member_id']]);
        db()->prepare('UPDATE password_tokens SET used_at = NOW() WHERE member_id = :m AND used_at IS NULL')->execute([':m' => $info['member_id']]);
        clear_attempts($info['email']);
        header('Location: /members/login.php?notice=password-set');
        exit;
    }
}

page_start('Choose a password', true);
if (!$info): ?>
  <h1 class="h1-small">This link no longer works</h1>
  <p>It may have been used already or it expired. <a href="/members/forgot.php">Ask for a new link</a>.</p>
<?php else: ?>
  <h1 class="h1-small"><?= $info['purpose'] === 'set' ? 'Choose your password' : 'Choose a new password' ?></h1>
  <?php if ($error): ?><p class="notice notice-error" role="alert"><?= e($error) ?></p><?php endif; ?>
  <form class="form" method="post" action="/members/set-password.php">
    <?= csrf_field() ?>
    <input type="hidden" name="token" value="<?= e($token) ?>">
    <div class="field"><label for="password">New password</label>
      <input id="password" name="password" type="password" autocomplete="new-password">
      <p class="hint">At least 8 characters, with an uppercase letter, a lowercase letter, a digit and a special character.</p></div>
    <div class="field"><label for="password_again">Repeat the password</label>
      <input id="password_again" name="password_again" type="password" autocomplete="new-password"></div>
    <div><button class="btn" type="submit">Save password</button></div>
  </form>
<?php endif;
page_end();