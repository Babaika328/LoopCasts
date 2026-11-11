<?php
declare(strict_types=1);
// POST /members/api/create.php   Header: Authorization: Bearer <key>   Body: order_id (form or JSON)
// Called by n8n after an order is paid. Gives the customer of that order access, exactly once per order:
//  - creates the member if the email is new (without a password) and returns a one-time link to choose one,
//  - extends the subscription of an existing member (from today, or from the end date if that is later).
require __DIR__ . '/../../lib/members.php';
require __DIR__ . '/../../lib/shop.php';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

function reply(int $status, array $data): never
{
    http_response_code($status);
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

// This key is for local development only and is not a real secret. n8n keeps it as a credential.
$key = getenv('MEMBERS_API_KEY') ?: 'test_local_members';
$given = preg_match('/^Bearer\s+(.+)$/i', $_SERVER['HTTP_AUTHORIZATION'] ?? '', $m) ? $m[1] : '';
if (!hash_equals($key, $given)) {
    reply(401, ['status' => 401, 'title' => 'Unauthorized', 'detail' => 'Missing or wrong API key']);
}
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    reply(405, ['status' => 405, 'title' => 'Method Not Allowed']);
}

$body = json_decode((string)file_get_contents('php://input'), true);
$orderId = (int)($_POST['order_id'] ?? (is_array($body) ? ($body['order_id'] ?? 0) : 0));
if ($orderId < 1) {
    reply(400, ['status' => 400, 'title' => 'Bad Request', 'detail' => 'order_id is required']);
}

$pdo = db();
$pdo->beginTransaction();
try {
    $st = $pdo->prepare('SELECT id, plan, name, email, status FROM orders WHERE id = :id FOR UPDATE');
    $st->execute([':id' => $orderId]);
    $order = $st->fetch();
    if (!$order) {
        $pdo->rollBack();
        reply(404, ['status' => 404, 'title' => 'Not Found', 'detail' => 'No order with this id']);
    }
    if ($order['status'] === 'failed') {
        $pdo->rollBack();
        reply(409, ['status' => 409, 'title' => 'Conflict', 'detail' => 'The order failed, no access is given']);
    }

    // Claim the order: only the first call for an order gets to give access.
    $claim = $pdo->prepare('UPDATE orders SET access_granted_at = NOW() WHERE id = :id AND access_granted_at IS NULL');
    $claim->execute([':id' => $orderId]);
    if ($claim->rowCount() !== 1) {
        $pdo->commit();
        reply(200, ['already_granted' => true, 'needs_password' => false, 'setup_url' => null]);
    }

    $email = strtolower($order['email']);
    $pdo->prepare('INSERT INTO members (email, name) VALUES (:e, :n) ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)')
        ->execute([':e' => $email, ':n' => $order['name']]);
    $memberId = (int)$pdo->lastInsertId();

    $st = $pdo->prepare('SELECT password_hash, access_until, created_at FROM members WHERE id = :id FOR UPDATE');
    $st->execute([':id' => $memberId]);
    $member = $st->fetch();

    // Date arithmetic is done by the database, which clamps month ends (31 Jan + 1 month = 28 Feb). The interval comes from
    // a fixed list, never from the request.
    $interval = ['monthly' => '1 MONTH', 'yearly' => '1 YEAR', 'team' => '1 YEAR'][$order['plan']] ?? null;
    $until = $member['access_until'];
    if ($interval !== null) {
        $pdo->exec('UPDATE members SET access_until = DATE_ADD(GREATEST(CURDATE(), COALESCE(access_until, CURDATE())), INTERVAL ' . $interval . ') WHERE id = ' . $memberId);
        $until = $pdo->query('SELECT access_until FROM members WHERE id = ' . $memberId)->fetchColumn();
    }

    $needsPassword = $member['password_hash'] === null;
    $setupUrl = $needsPassword ? site_url() . '/members/set-password.php?token=' . new_token($memberId, 'set') : null;
    $pdo->commit();
} catch (Throwable $e) {
    if ($pdo->inTransaction()) {
        $pdo->rollBack();
    }
    error_log('members/api/create.php: ' . $e->getMessage());
    reply(500, ['status' => 500, 'title' => 'Server error']);
}

reply(200, ['already_granted' => false, 'member_id' => $memberId, 'needs_password' => $needsPassword,
            'setup_url' => $setupUrl, 'access_until' => $until, 'name' => $order['name'], 'email' => $email]);