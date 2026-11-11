<?php
declare(strict_types=1);

// What we sell. Prices are in cents and exclude VAT (handbook: "All prices without VAT").
const PLANS = [
    'monthly' => ['name' => 'Monthly',       'cents' => 1500,  'price' => '€15 per month', 'note' => 'Access to everything. Billed every month.'],
    'yearly'  => ['name' => 'Yearly',        'cents' => 14900, 'price' => '€149 per year', 'note' => 'Access to everything.'],
    'team'    => ['name' => 'Team licence',  'cents' => 59900, 'price' => '€599 per year', 'note' => 'Five seats. After payment you send us the five names.'],
    'single'  => ['name' => 'Single course', 'cents' => 3900,  'price' => '€39',           'note' => 'Lifetime access to one course.'],
];
const COURSES = [
    'n8n basics', 'Webhooks from zero', 'REST APIs for data people',
    'Shell scripting that saves your week', 'Cron and schedulers', 'GitHub Actions in practice',
];
const COUNTRIES = [
    'BE' => 'Belgium', 'NL' => 'Netherlands', 'FR' => 'France', 'DE' => 'Germany',
    'LU' => 'Luxembourg', 'IT' => 'Italy', 'ES' => 'Spain', 'IE' => 'Ireland',
];
const VAT_PERCENT = 21;

// The VAT rule. A business in another EU country that gives a VAT number pays no Belgian VAT (reverse charge).
// Everyone else pays Belgian VAT. Open point for the accountant: private customers in other EU countries.
// The VAT number itself is only format-checked here; a real validity check (VIES) comes later.
function vat_rule(string $country, bool $isCompany, string $vatNumber): string
{
    if ($isCompany && $vatNumber !== '' && $country !== 'BE') {
        return 'reverse_charge';
    }
    return 'belgian_21';
}

function vat_cents(int $exclCents, string $rule): int
{
    return $rule === 'reverse_charge' ? 0 : intdiv($exclCents * VAT_PERCENT + 50, 100);
}

const PLAN_NAMES = ['monthly' => 'Monthly subscription', 'yearly' => 'Yearly subscription', 'team' => 'Team licence', 'single' => 'Single course'];