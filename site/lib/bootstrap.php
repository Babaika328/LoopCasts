<?php
declare(strict_types=1);

// Database connection. The defaults are DDEV's local ones (not secrets). Anything real comes from the environment.
function db(): PDO
{
    static $pdo = null;
    if ($pdo === null) {
        $host = getenv('DB_HOST') ?: 'db';
        $port = getenv('DB_PORT') ?: '3306';
        $name = getenv('DB_NAME') ?: 'db';
        $user = getenv('DB_USER') ?: 'db';
        $pass = getenv('DB_PASSWORD') ?: 'db';
        $pdo = new PDO("mysql:host=$host;port=$port;dbname=$name;charset=utf8mb4", $user, $pass, [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES   => false,
            PDO::MYSQL_ATTR_INIT_COMMAND => 'SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci',
        ]);
    }
    return $pdo;
}

function e(string $s): string
{
    return htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function euro(int $cents): string
{
    return '€' . number_format($cents / 100, 2, '.', '');
}

// Sent with every PHP page. The CSP only allows our own scripts and styles (no inline code), blocks framing of our
// forms (clickjacking) and limits where forms can post to. Static files such as index.html need the same headers
// from the web server in production.
function send_security_headers(): void
{
    header('X-Content-Type-Options: nosniff');
    header('X-Frame-Options: DENY');
    header('Referrer-Policy: strict-origin-when-cross-origin');
    header('Permissions-Policy: camera=(), microphone=(), geolocation=()');
    header("Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; form-action 'self'; frame-ancestors 'none'; base-uri 'self'");
}

if (PHP_SAPI !== 'cli') {
    send_security_headers();
}