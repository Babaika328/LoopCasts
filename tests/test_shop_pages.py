"""Everything a visitor can do on the shop side: every plan, every course, every country, the checkout and the result pages."""
import re

import pytest

from conftest import api_payment, new_payment, pay, place_order, site

COURSES = ["n8n basics", "Webhooks from zero", "REST APIs for data people",
           "Shell scripting that saves your week", "Cron and schedulers", "GitHub Actions in practice"]
COUNTRIES = ["BE", "NL", "FR", "DE", "LU", "IT", "ES", "IE"]
FOREIGN = {"NL": "NL853123456B01", "FR": "FR12345678901", "DE": "DE123456789", "LU": "LU12345678",
           "IT": "IT12345678901", "ES": "ESB12345678", "IE": "IE1234567AB"}
PLANS = {"monthly": "Monthly", "yearly": "Yearly", "team": "Team licence", "single": "Single course"}


# --- the order page ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("plan,name", PLANS.items())
def test_every_plan_has_an_order_page(plan, name):
    status, headers, body = site("GET", f"/order.php?plan={plan}")
    assert status == 200 and f"Order: {name}" in body and "<form" in body


def test_an_unknown_plan_falls_back_to_the_yearly_plan():
    assert "Order: Yearly" in site("GET", "/order.php?plan=free-forever")[2]


@pytest.mark.parametrize("course", COURSES)
def test_every_single_course_costs_47_19_with_vat(course):
    pid, _ = new_payment(plan="single", course=course)
    status, payment = api_payment(pid)
    assert payment["amount"]["value"] == "47.19" and course in payment["description"]
    assert payment["metadata"]["course"] == course


def test_a_course_that_does_not_exist_is_refused():
    status, headers, body, _ = place_order(plan="single", course="Hacking for beginners")
    assert status == 200 and "location" not in headers and "Choose a course" in body


def test_a_single_course_order_without_a_course_is_refused():
    status, headers, body, _ = place_order(plan="single", course="")
    assert status == 200 and "location" not in headers and "Choose a course" in body


@pytest.mark.parametrize("country", COUNTRIES)
def test_a_private_customer_in_any_country_pays_belgian_vat(country):
    pid, _ = new_payment(plan="yearly", country=country)
    payment = api_payment(pid)[1]
    assert payment["amount"]["value"] == "180.29" and payment["metadata"]["vat_rule"] == "belgian_21"


@pytest.mark.parametrize("country,vat", FOREIGN.items())
def test_a_foreign_business_with_a_vat_number_pays_no_belgian_vat(country, vat):
    pid, _ = new_payment(plan="yearly", country=country, company="Firma BV", vat=vat)
    payment = api_payment(pid)[1]
    assert payment["amount"]["value"] == "149.00" and payment["metadata"]["vat_rule"] == "reverse_charge"
    assert payment["metadata"]["vat_number"] == vat


def test_vat_numbers_are_cleaned_up_before_they_are_stored():
    pid, _ = new_payment(country="NL", company="Firma BV", vat="nl 8531.23.456 b01")
    assert api_payment(pid)[1]["metadata"]["vat_number"] == "NL853123456B01"


def test_a_belgian_business_still_pays_belgian_vat():
    pid, _ = new_payment(country="BE", company="Firma NV", vat="BE0123456789")
    payment = api_payment(pid)[1]
    assert payment["amount"]["value"] == "180.29" and payment["metadata"]["vat_rule"] == "belgian_21"


def test_a_country_that_is_not_offered_is_refused():
    status, headers, body, _ = place_order(country="XX")
    assert status == 200 and "location" not in headers and "Choose a country" in body


def test_the_form_keeps_what_was_typed_after_an_error():
    status, _, body, _ = place_order(email="not-an-email", name="Eva Janssens")
    assert 'value="Eva Janssens"' in body and "valid email" in body


def test_whatever_is_typed_is_escaped_when_the_form_is_shown_again():
    evil = '"><script>alert(1)</script><img src=x onerror=alert(2)>'
    status, _, body, _ = place_order(email="x", name=evil, company=evil, vat=evil, country="NL")
    assert "<script>alert(1)</script>" not in body and "<img src=x" not in body
    assert "&lt;script&gt;" in body


def test_the_error_message_is_red_and_not_green():
    body = place_order(email="x")[2]
    assert 'class="notice notice-error"' in body


# --- checkout and the result pages ------------------------------------------------------------------------------

def test_an_open_payment_shows_the_checkout_with_the_amount():
    pid, _ = new_payment(plan="team")
    status, _, body = site("GET", f"/pay/checkout.php?id={pid}")
    assert status == 200 and "€724.79" in body and "Team licence" in body
    assert "Pay</button>" in body and "Payment fails" in body and "Cancel" in body


def test_paying_shows_the_result_and_then_the_thank_you_page():
    pid, _ = new_payment()
    assert "Payment paid" in pay(pid, "pay")
    status, _, body = site("GET", f"/order-done.php?id={pid}")
    assert status == 200 and "your payment was received" in body and "€180.29" in body


@pytest.mark.parametrize("action,word", [("fail", "failed"), ("cancel", "canceled")])
def test_a_failed_or_cancelled_payment_shows_the_try_again_page(action, word):
    pid, _ = new_payment()
    assert f"Payment {word}" in pay(pid, action)
    body = site("GET", f"/order-done.php?id={pid}")[2]
    assert "did not go through" in body and "Nothing was charged" in body


def test_an_unfinished_payment_offers_to_continue():
    pid, _ = new_payment()
    body = site("GET", f"/order-done.php?id={pid}")[2]
    assert "not finished" in body and f"/pay/checkout.php?id={pid}" in body


def test_unknown_payments_give_a_not_found_page():
    assert site("GET", "/pay/checkout.php?id=tr_test_000000000000")[0] == 404
    assert site("GET", "/order-done.php?id=tr_test_000000000000")[0] == 404
    assert site("GET", "/order-done.php")[0] == 404


# --- the home page ----------------------------------------------------------------------------------------------

def test_the_home_page_links_to_every_plan_and_to_log_in():
    body = site("GET", "/index.html")[2]
    assert set(re.findall(r'href="order\.php\?plan=(\w+)"', body)) == set(PLANS)
    assert 'href="/members/"' in body
    for plan in PLANS:
        assert site("GET", f"/order.php?plan={plan}")[0] == 200
    assert site("GET", "/members/login.php")[0] == 200