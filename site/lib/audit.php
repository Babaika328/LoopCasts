<?php
declare(strict_types=1);
require_once __DIR__ . '/members.php';

// Writes one line to the audit log: who (the logged-in person), what, about which record, and from which address.
function audit(string $action, ?string $target = null, ?string $details = null): void
{
    $who = current_member();
    db()->prepare('INSERT INTO audit_log (actor_id, actor_email, action, target, details, ip) VALUES (:a, :e, :ac, :t, :d, :ip)')->execute([
        ':a' => $who['id'] ?? null,
        ':e' => $who['email'] ?? 'anonymous',
        ':ac' => substr($action, 0, 60),
        ':t' => $target === null ? null : substr($target, 0, 120),
        ':d' => $details === null ? null : substr($details, 0, 500),
        ':ip' => client_ip(),
    ]);
}