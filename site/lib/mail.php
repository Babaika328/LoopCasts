<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';

// Sends one email with a plain-text part and, when given, an HTML part (multipart/alternative). Every part is base64
// encoded, so long lines, non-ASCII text and lines that start with a dot can never break the message.
// If SMTP_HOST is set (or the site runs in DDEV, where Mailpit catches all mail on port 1025) it talks to that SMTP
// server directly, so a failure is visible in the log. Otherwise it falls back to PHP's mail().
// The small SMTP client is meant for a mail catcher or an internal relay without a login. A production mail server with
// TLS and a password needs a proper library.
function send_mail(string $to, string $subject, string $text, ?string $html = null): bool
{
    if (!filter_var($to, FILTER_VALIDATE_EMAIL)) {
        return false;
    }
    $from = getenv('MAIL_FROM') ?: 'LoopCasts <noreply@loopcasts.test>';
    [$headers, $body] = build_mime($from, $to, $subject, $text, $html);
    $host = getenv('SMTP_HOST') ?: (getenv('IS_DDEV_PROJECT') ? '127.0.0.1' : '');
    if ($host === '') {
        $headers = array_filter($headers, fn ($h) => !preg_match('/^(To|Subject):/i', $h));
        return @mail($to, $subject, $body, implode("\r\n", $headers));
    }
    return smtp_send($host, (int)(getenv('SMTP_PORT') ?: 1025), $from, $to, implode("\r\n", $headers) . "\r\n\r\n" . $body);
}

function build_mime(string $from, string $to, string $subject, string $text, ?string $html): array
{
    $subject = str_replace(["\r", "\n"], ' ', $subject);
    $encoded = preg_match('/[^\x20-\x7e]/', $subject) ? '=?UTF-8?B?' . base64_encode($subject) . '?=' : $subject;
    $headers = ["From: $from", "To: $to", "Subject: $encoded", 'Date: ' . date('r'),
        'Message-ID: <' . bin2hex(random_bytes(8)) . '@loopcasts>', 'MIME-Version: 1.0'];
    $b64 = fn (string $s): string => chunk_split(base64_encode($s), 76, "\r\n");
    if ($html === null) {
        $headers[] = 'Content-Type: text/plain; charset=UTF-8';
        $headers[] = 'Content-Transfer-Encoding: base64';
        return [$headers, $b64($text)];
    }
    $boundary = 'lc_' . bin2hex(random_bytes(12));
    $headers[] = "Content-Type: multipart/alternative; boundary=\"$boundary\"";
    $body = "--$boundary\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n" . $b64($text)
        . "--$boundary\r\nContent-Type: text/html; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n" . $b64($html)
        . "--$boundary--\r\n";
    return [$headers, $body];
}

function smtp_send(string $host, int $port, string $from, string $to, string $message): bool
{
    $fp = @stream_socket_client("tcp://$host:$port", $errno, $errstr, 5);
    if (!$fp) {
        error_log("smtp_send: cannot connect to $host:$port ($errstr)");
        return false;
    }
    stream_set_timeout($fp, 5);
    $read = function () use ($fp): string {
        $out = '';
        while (($line = fgets($fp, 515)) !== false) {
            $out .= $line;
            if (strlen($line) < 4 || $line[3] === ' ') {
                break;
            }
        }
        return $out;
    };
    $say = function (string $command, string $expect) use ($fp, $read): bool {
        fwrite($fp, $command . "\r\n");
        return str_starts_with($read(), $expect);
    };
    $address = preg_match('/<([^>]+)>/', $from, $m) ? $m[1] : $from;
    $ok = str_starts_with($read(), '220')
        && $say('EHLO loopcasts', '250')
        && $say("MAIL FROM:<$address>", '250')
        && $say("RCPT TO:<$to>", '250')
        && $say('DATA', '354')
        && $say($message . "\r\n.", '250');   // the message ends with a line break, so this closes it with "\r\n.\r\n"
    if ($ok) {
        $say('QUIT', '221');
    } else {
        error_log("smtp_send: the server at $host:$port refused the message");
    }
    fclose($fp);
    return $ok;
}

// The same look as the invoice and welcome emails (mint and white). $introHtml and $noteHtml are written in code, never
// from user input; the button address is escaped here.
function email_html(string $heading, string $introHtml, ?string $buttonUrl = null, ?string $buttonLabel = null, string $noteHtml = ''): string
{
    $button = ($buttonUrl && $buttonLabel)
        ? '<p style="margin:24px 0;"><a href="' . e($buttonUrl) . '" style="display:inline-block;background:#1f7a5c;color:#ffffff;text-decoration:none;font-weight:bold;padding:14px 24px;border-radius:10px;">' . e($buttonLabel) . '</a></p>'
        : '';
    return '<!doctype html><html><body style="margin:0;background:#eaf7f1;font-family:Arial,Helvetica,sans-serif;color:#17332a;">'
        . '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eaf7f1;padding:24px 12px;"><tr><td align="center">'
        . '<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;background:#ffffff;border-radius:12px;">'
        . '<tr><td style="padding:28px 32px 8px;font-size:22px;font-weight:bold;">LoopCasts</td></tr>'
        . '<tr><td style="padding:8px 32px 0;"><div style="font-size:26px;font-weight:bold;color:#1f7a5c;">' . e($heading) . '</div></td></tr>'
        . '<tr><td style="padding:16px 32px 8px;font-size:14px;line-height:1.6;"><p style="margin:0 0 16px;">' . $introHtml . '</p>' . $button
        . ($noteHtml !== '' ? '<p style="margin:0 0 24px;color:#4a6b5e;font-size:13px;">' . $noteHtml . '</p>' : '')
        . '</td></tr></table></td></tr></table></body></html>';
}

// The reset email: returns [subject, plain text, HTML].
function reset_email(string $link): array
{
    $text = "Hello,\n\nSomeone asked to reset the password of this LoopCasts account.\n"
        . "If it was you, choose a new password here (the link works for 2 hours, once):\n\n$link\n\n"
        . "If it was not you, ignore this email: nothing changes.\n\nLoopCasts support\n";
    $html = email_html('Reset your password',
        'Someone asked to reset the password of this LoopCasts account. If it was you, choose a new password with the button below.',
        $link, 'Choose a new password',
        'The link works for 2 hours and only once. If it was not you, ignore this email: nothing changes. We will never ask for your password by email.');
    return ['Reset your LoopCasts password', $text, $html];
}