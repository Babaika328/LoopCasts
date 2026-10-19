<?php
declare(strict_types=1);
// GET /pay/api.php?id=tr_test_...   Header: Authorization: Bearer <key>
// Like Mollie's GET /v2/payments/{id}. n8n calls this to learn the real status after a webhook.
require __DIR__ . '/../lib/bootstrap.php';
require __DIR__ . '/../lib/payments.php';

header('Content-Type: application/json; charset=utf-8');

// This key is for the simulator only and is not a real secret. n8n stores it as a credential.
$key = getenv('SIM_API_KEY') ?: 'test_local_simulator';
$given = '';
if (preg_match('/^Bearer\s+(.+)$/i', $_SERVER['HTTP_AUTHORIZATION'] ?? '', $m)) { $given = $m[1]; }
if (!hash_equals($key, $given)) {
    http_response_code(401);
    echo json_encode(['status' => 401, 'title' => 'Unauthorized Request', 'detail' => 'Missing or wrong API key']);
    exit;
}

$p = find_payment((string)($_GET['id'] ?? ''));
if ($p === null) {
    http_response_code(404);
    echo json_encode(['status' => 404, 'title' => 'Not Found', 'detail' => 'No payment with this id']);
    exit;
}
echo json_encode(payment_json($p), JSON_UNESCAPED_UNICODE);
