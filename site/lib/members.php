<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';

// A real bcrypt hash of a throwaway string. Used when the email is unknown, so that checking a wrong email
// takes as long as checking a wrong password and the answer does not reveal who is a member.
const DUMMY_HASH = '$2y$10$XvYFoa34uvZO/tGgMq6ko.Hv5CpwkA826OJOSPk4.G6/llnmMX19e';

// Links in emails must never be built from the request's Host header (an attacker could send a reset link that
// points to his own site). They come from configuration.
function site_url(): string
{
    return rtrim(getenv('SITE_URL') ?: getenv('DDEV_PRIMARY_URL') ?: 'http://localhost', '/');
}

function start_session(): void
{
    if (session_status() === PHP_SESSION_ACTIVE) {
        return;
    }
    $https = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') || (($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '') === 'https');
    session_name('loopcasts');
    ini_set('session.use_strict_mode', '1');
    session_set_cookie_params(['lifetime' => 0, 'path' => '/', 'secure' => $https, 'httponly' => true, 'samesite' => 'Lax']);
    session_start();
}

function csrf_token(): string
{
    start_session();
    if (empty($_SESSION['csrf'])) {
        $_SESSION['csrf'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf'];
}

function csrf_field(): string
{
    return '<input type="hidden" name="csrf" value="' . e(csrf_token()) . '">';
}

function csrf_ok(): bool
{
    start_session();
    $sent = (string)($_POST['csrf'] ?? '');
    return $sent !== '' && isset($_SESSION['csrf']) && hash_equals($_SESSION['csrf'], $sent);
}

function current_member(): ?array
{
    start_session();
    $id = $_SESSION['member_id'] ?? null;
    if (!$id) {
        return null;
    }
    $st = db()->prepare('SELECT id, email, name, access_until, (access_until IS NOT NULL AND access_until >= CURDATE()) AS active FROM members WHERE id = :id');
    $st->execute([':id' => (int)$id]);
    return $st->fetch() ?: null;
}

function client_ip(): string
{
    return substr((string)($_SERVER['REMOTE_ADDR'] ?? '0.0.0.0'), 0, 45);
}

// At most 5 failures per email and 30 per address in 15 minutes.
function throttled(string $key): bool
{
    $byKey = db()->prepare('SELECT COUNT(*) FROM login_attempts WHERE email = :k AND attempted_at > DATE_SUB(NOW(), INTERVAL 15 MINUTE)');
    $byKey->execute([':k' => $key]);
    $byIp = db()->prepare('SELECT COUNT(*) FROM login_attempts WHERE ip = :ip AND attempted_at > DATE_SUB(NOW(), INTERVAL 15 MINUTE)');
    $byIp->execute([':ip' => client_ip()]);
    return (int)$byKey->fetchColumn() >= 5 || (int)$byIp->fetchColumn() >= 30;
}

function record_attempt(string $key): void
{
    db()->prepare('INSERT INTO login_attempts (email, ip) VALUES (:k, :ip)')->execute([':k' => substr($key, 0, 200), ':ip' => client_ip()]);
}

function clear_attempts(string $key): void
{
    db()->prepare('DELETE FROM login_attempts WHERE email = :k')->execute([':k' => $key]);
}

// Creates a one-time link secret. Returns the plain secret (to put in the link); the database keeps only its hash.
// 'set' links (first password) last 7 days, 'reset' links 2 hours. Older unused links of the member stop working.
function new_token(int $memberId, string $purpose): string
{
    $plain = bin2hex(random_bytes(32));
    db()->prepare('UPDATE password_tokens SET used_at = NOW() WHERE member_id = :m AND used_at IS NULL')->execute([':m' => $memberId]);
    $hours = $purpose === 'set' ? 168 : 2;
    db()->prepare('INSERT INTO password_tokens (member_id, token_hash, purpose, expires_at) VALUES (:m, :h, :p, DATE_ADD(NOW(), INTERVAL ' . $hours . ' HOUR))')
        ->execute([':m' => $memberId, ':h' => hash('sha256', $plain), ':p' => $purpose]);
    return $plain;
}

function find_valid_token(string $plain): ?array
{
    if (!preg_match('/^[0-9a-f]{64}$/', $plain)) {
        return null;
    }
    $st = db()->prepare('SELECT t.id, t.member_id, t.purpose, m.email FROM password_tokens t JOIN members m ON m.id = t.member_id WHERE t.token_hash = :h AND t.used_at IS NULL AND t.expires_at > NOW()');
    $st->execute([':h' => hash('sha256', $plain)]);
    return $st->fetch() ?: null;
}

function send_mail(string $to, string $subject, string $body): bool
{
    $from = getenv('MAIL_FROM') ?: 'LoopCasts <noreply@loopcasts.test>';
    return @mail($to, $subject, $body, "From: $from\r\nContent-Type: text/plain; charset=UTF-8");
}