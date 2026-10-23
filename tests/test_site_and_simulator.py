"""Tests that need only the site and the database (no n8n)."""
import pytest

from conftest import api_payment, new_payment, pay, place_order, site

# (plan, country, company, vat number, expected total in cents, expected VAT rule)
# The totals are the real ones from the invoice register: 149 + VAT = 180.29, 15 -> 18.15, 39 -> 47.19, 599 -> 724.79.
PRICES = [
    ("yearly",  "BE", None,       None,             18029, "belgian_21"),
    ("monthly", "BE", None,       None,              1815, "belgian_21"),
    ("single",  "BE", None,       None,              4719, "belgian_21"),
    ("team",    "BE", None,       None,             72479, "belgian_21"),
    ("yearly",  "BE", "Firma NV", "BE0123456789",   18029, "belgian_21"),       # Belgian company still pays Belgian VAT
    ("yearly",  "NL", "Firma BV", "NL853123456B01", 14900, "reverse_charge"),   # foreign EU business: no Belgian VAT
    ("yearly",  "NL", None,       None,             18029, "belgian_21"),       # private person abroad: open point for the accountant
]


def test_home_page_loads():
    status, _, body = site("GET", "/index.html")
    assert status == 200 and "LoopCasts" in body


def test_api_refuses_missing_and_wrong_key():
    assert api_payment("tr_test_000000000000", key=None)[0] == 401
    assert api_payment("tr_test_000000000000", key="not-the-key")[0] == 401


def test_api_says_not_found_for_unknown_payment():
    assert api_payment("tr_test_000000000000")[0] == 404


@pytest.mark.parametrize("plan,country,company,vat,total,rule", PRICES)
def test_amount_and_vat_rule(plan, country, company, vat, total, rule):
    pid, _ = new_payment(plan=plan, country=country, company=company, vat=vat)
    status, payment = api_payment(pid)
    assert status == 200
    assert payment["status"] == "open"
    assert payment["amount"]["value"] == f"{total / 100:.2f}"
    assert payment["metadata"]["vat_rule"] == rule


def test_company_without_vat_number_is_refused():
    status, headers, body, _ = place_order(company="Firma BV", vat="", country="NL")
    assert status == 200 and "location" not in headers
    assert "Enter the VAT number" in body


def test_vat_number_with_wrong_format_is_refused():
    status, headers, body, _ = place_order(company="Firma BV", vat="12345", country="NL")
    assert status == 200 and "location" not in headers
    assert "does not look like a VAT number" in body


def test_bad_email_is_refused():
    status, headers, body, _ = place_order(email="not-an-email")
    assert status == 200 and "location" not in headers
    assert "valid email" in body


def test_customer_text_is_escaped_on_the_page():
    status, _, body, _ = place_order(email="x", company="<script>alert(1)</script>", vat="")
    assert "<script>alert(1)</script>" not in body


def test_a_finished_payment_cannot_change_status():
    pid, _ = new_payment()
    pay(pid, "pay")
    pay(pid, "fail")
    assert api_payment(pid)[1]["status"] == "paid"
