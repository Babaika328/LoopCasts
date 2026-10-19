<?php
declare(strict_types=1);

// A small payment provider simulator. It copies how Mollie works:
// a payment is created, the customer pays on a test checkout page, the provider calls our webhook
// with ONLY the payment id, and we fetch the payment to learn its real status.

function create_payment(int $amountCents, string $description, array $metadata): string
{
    $id = 'tr_test_' . bin2hex(random_bytes(6));
    $webhook = getenv('PAYMENT_WEBHOOK_URL') ?: 'http://n8n:5678/webhook/payment';
    $st = db()->prepare(
        'INSERT INTO payments (id, amount_cents, description, metadata, webhook_url, redirect_url)
         VALUES (:id, :amount, :descr, :meta, :hook, :redirect)'
    );
    $st->execute([
        ':id' => $id, ':amount' => $amountCents, ':descr' => $description,
        ':meta' => json_encode($metadata, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR),
        ':hook' => $webhook, ':redirect' => '/order-done.php?id=' . $id,
    ]);
    return $id;
}

function find_payment(string $id): ?array
{
    $st = db()->prepare('SELECT * FROM payments WHERE id = :id');
    $st->execute([':id' => $id]);
    return $st->fetch() ?: null;
}

// Sends the webhook: a form-encoded POST with only the payment id, no status and no signature.
// Returns a short human-readable result, so a failed delivery is never silent.
function send_webhook(string $url, string $paymentId): string
{
    $ctx = stream_context_create(['http' => [
        'method' => 'POST',
        'header' => "Content-Type: application/x-www-form-urlencoded\r\n",
        'content' => http_build_query(['id' => $paymentId]),
        'timeout' => 3,
        'ignore_errors' => true,
    ]]);
    $body = @file_get_contents($url, false, $ctx);
    if ($body === false) {
        return 'failed (no answer from ' . $url . ')';
    }
    $code = 0;
    foreach ($http_response_header ?? [] as $h) {
        if (preg_match('#^HTTP/\S+\s+(\d{3})#', $h, $m)) { $code = (int)$m[1]; }
    }
    return 'HTTP ' . $code;
}

// What the "provider API" returns, shaped like Mollie's payment object.
function payment_json(array $p): array
{
    return [
        'resource'    => 'payment',
        'id'          => $p['id'],
        'status'      => $p['status'],
        'amount'      => ['value' => number_format($p['amount_cents'] / 100, 2, '.', ''), 'currency' => $p['currency']],
        'description' => $p['description'],
        'metadata'    => json_decode($p['metadata'], true),
        'createdAt'   => $p['created_at'],
        'paidAt'      => $p['paid_at'],
    ];
}