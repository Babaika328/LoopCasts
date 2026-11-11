<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';

function page_start(string $title, bool $noCache = false): void
{
    header('Content-Type: text/html; charset=utf-8');
    if ($noCache) {
        header('Cache-Control: no-store');
        header('Referrer-Policy: no-referrer');   // a link with a secret in it must not leak through the Referer header
    }
    echo '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        . '<title>' . e($title) . ': LoopCasts</title><link rel="stylesheet" href="/style.css"></head><body>'
        . '<a class="skip" href="#main">Skip to content</a>'
        . '<header class="bar"><div class="wrap bar-inner"><a class="brand" href="/index.html">LoopCasts</a>'
        . '<nav aria-label="Main"><a href="/index.html#courses">Courses</a><a href="/index.html#pricing">Pricing</a><a href="/members/">Log in</a></nav></div></header>'
        . '<main id="main" class="wrap narrow section">';
}

function page_end(): void
{
    echo '</main><footer class="foot"><div class="wrap"><p><strong>LoopCasts BV</strong></p><p>Fietsstraat 12 bus 2, 9000 Gent</p>'
        . '<p class="fine">&copy; 2026 LoopCasts BV</p></div></footer></body></html>';
}