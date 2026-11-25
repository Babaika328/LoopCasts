<?php
declare(strict_types=1);
require __DIR__ . '/../lib/members.php';
require __DIR__ . '/../lib/layout.php';
require __DIR__ . '/../lib/audit.php';

$member = current_member();
if (!$member) {
    header('Location: /members/login.php');
    exit;
}

$notice = null;
$error = null;

function open_request(int $memberId, string $category): bool
{
    $st = db()->prepare("SELECT COUNT(*) FROM tickets WHERE member_id = :m AND category = :c AND status IN ('new','needs_human','drafted')");
    $st->execute([':m' => $memberId, ':c' => $category]);
    return (int)$st->fetchColumn() > 0;
}

function new_request(array $member, string $category, string $subject, string $body): void
{
    db()->prepare("INSERT INTO tickets (source, member_id, from_email, subject, body, category, needs_human, status)
                   VALUES ('profile', :m, :e, :s, :b, :c, 1, 'needs_human')")
        ->execute([':m' => $member['id'], ':e' => $member['email'], ':s' => $subject, ':b' => $body, ':c' => $category]);
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $action = (string)($_POST['action'] ?? '');
    if (!csrf_ok()) {
        http_response_code(400);
        $error = 'Your session expired. Please reload the page and try again.';
    } elseif ($action === 'cancel') {
        if ($member['access_until'] === null) {
            $error = 'You have no subscription to cancel.';
        } elseif (open_request((int)$member['id'], 'cancel_or_refund')) {
            $notice = 'We already have your request. A person will answer by email.';
        } else {
            // At most 500 characters. preg_match with the u flag cuts on character borders without needing the mbstring extension.
            $reason = preg_match('/^.{0,500}/su', trim((string)($_POST['reason'] ?? '')), $cut) ? $cut[0] : '';
            new_request($member, 'cancel_or_refund', 'Cancel subscription request', $reason !== '' ? $reason : '(no reason given)');
            audit('request_cancel', 'member:' . $member['id']);
            $notice = 'We received your request. A person will answer by email. Cancelling is decided by a person, not by this page.';
        }
    } elseif ($action === 'delete') {
        $key = 'delete:' . $member['id'];
        if (throttled($key)) {
            http_response_code(429);
            $error = 'Too many attempts. Wait 15 minutes and try again.';
        } else {
            $st = db()->prepare('SELECT password_hash FROM members WHERE id = :id');
            $st->execute([':id' => $member['id']]);
            if (!password_verify((string)($_POST['password'] ?? ''), (string)$st->fetchColumn())) {
                record_attempt($key);
                $error = 'Your password is not right.';
            } elseif (open_request((int)$member['id'], 'privacy_request')) {
                $notice = 'We already have your request. A person will answer by email.';
            } else {
                new_request($member, 'privacy_request', 'Delete my account', 'Deletion of the account was requested by the member.');
                audit('request_delete', 'member:' . $member['id']);
                clear_attempts($key);
                $notice = 'We received your request. A person will answer by email.';
            }
        }
    }
}

$st = db()->prepare("SELECT received_at, subject, status FROM tickets WHERE member_id = :m AND source = 'profile' ORDER BY id DESC LIMIT 10");
$st->execute([':m' => $member['id']]);
$requests = $st->fetchAll();

page_start('Your details and privacy', true);
?>
<h1 class="h1-small">Your details and privacy</h1>
<?php if ($notice): ?><p class="notice"><?= e($notice) ?></p><?php endif; ?>
<?php if ($error): ?><p class="notice notice-error" role="alert"><?= e($error) ?></p><?php endif; ?>

<h2>Your details</h2>
<dl class="facts">
  <dt>Name</dt><dd><?= e($member['name']) ?></dd>
  <dt>Email</dt><dd><?= e($member['email']) ?></dd>
</dl>
<p><a href="/members/password.php">Change your password</a></p>

<h2>Your data</h2>
<p>Download everything we hold about you (profile, orders, requests) as a file.</p>
<p><a class="btn btn-quiet" href="/members/data.php">Download my data</a></p>

<h2>Cancel your subscription</h2>
<?php if ($member['access_until'] === null): ?>
  <p>You have no subscription.</p>
<?php else: ?>
  <p>Send us a request. A person looks at it and answers by email.</p>
  <form class="form" method="post" action="/members/profile.php">
    <?= csrf_field() ?>
    <input type="hidden" name="action" value="cancel">
    <div class="field"><label for="reason">Why do you want to cancel? (optional)</label>
      <textarea id="reason" name="reason" rows="3" maxlength="500"></textarea></div>
    <div><button class="btn btn-quiet" type="submit">Request cancellation</button></div>
  </form>
<?php endif; ?>

<h2>Delete your account</h2>
<p>We remove your login and your profile. Invoices stay, because the law makes us keep them for seven years. A person handles the request and answers by email.</p>
<form class="form" method="post" action="/members/profile.php">
  <?= csrf_field() ?>
  <input type="hidden" name="action" value="delete">
  <div class="field"><label for="password">Your password, to confirm it is you</label>
    <input id="password" name="password" type="password" autocomplete="current-password"></div>
  <div><button class="btn btn-quiet" type="submit">Request deletion</button></div>
</form>

<?php if ($requests): ?>
<h2>Your requests</h2>
<ul class="courses">
<?php foreach ($requests as $r): ?>
  <li><span class="c-title"><?= e($r['subject']) ?></span><span><?= e(date('d/m/Y', strtotime($r['received_at']))) ?></span>
      <span><?= $r['status'] === 'closed' ? 'Done' : 'Open' ?></span></li>
<?php endforeach; ?>
</ul>
<?php endif; ?>
<p class="stack-top"><a href="/members/">Back to your account</a></p>
<?php page_end();