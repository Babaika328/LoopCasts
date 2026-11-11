<?php
declare(strict_types=1);
require __DIR__ . '/../lib/members.php';
require __DIR__ . '/../lib/layout.php';

start_session();
if (current_member()) {
    header('Location: /members/');
    exit;
}

$error = null;
$email = '';
$notice = ($_GET['notice'] ?? '') === 'password-set' ? 'Your password is set. You can log in now.' : null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $email = strtolower(trim((string)($_POST['email'] ?? '')));
    $password = (string)($_POST['password'] ?? '');

    if (!csrf_ok()) {
        http_response_code(400);
        $error = 'Your session expired. Please try again.';
    } elseif (throttled($email)) {
        http_response_code(429);
        $error = 'Too many attempts. Wait 15 minutes and try again.';
    } else {
        $st = db()->prepare('SELECT id, password_hash FROM members WHERE email = :e');
        $st->execute([':e' => $email]);
        $row = $st->fetch();
        // Always run one password check, also for unknown emails or members without a password yet.
        $valid = password_verify($password, $row['password_hash'] ?? DUMMY_HASH);
        if ($row && $row['password_hash'] !== null && $valid) {
            session_regenerate_id(true);
            $_SESSION['member_id'] = (int)$row['id'];
            db()->prepare('UPDATE members SET last_login_at = NOW() WHERE id = :id')->execute([':id' => $row['id']]);
            clear_attempts($email);
            header('Location: /members/');
            exit;
        }
        record_attempt($email);
        $error = 'Wrong email or password.';   // the same text for an unknown email and a wrong password
    }
}

page_start('Log in');
?>
<h1 class="h1-small">Log in</h1>
<?php if ($notice): ?><p class="notice"><?= e($notice) ?></p><?php endif; ?>
<?php if ($error): ?><p class="notice" role="alert"><?= e($error) ?></p><?php endif; ?>
<form class="form" method="post" action="/members/login.php">
  <?= csrf_field() ?>
  <div class="field"><label for="email">Email address</label>
    <input id="email" name="email" type="email" autocomplete="username" value="<?= e($email) ?>"></div>
  <div class="field"><label for="password">Password</label>
    <input id="password" name="password" type="password" autocomplete="current-password"></div>
  <div><button class="btn" type="submit">Log in</button></div>
</form>
<p><a href="/members/forgot.php">Forgot your password?</a></p>
<?php page_end();