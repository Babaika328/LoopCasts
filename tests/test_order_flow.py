"""The full path: form, payment, webhook, n8n, order table. Needs n8n with the workflow ACTIVE."""
import time

import pytest

from conftest import (api_payment, db, new_payment, order_count, pay, post_webhook, wait_for_orders)

pytestmark = pytest.mark.n8n
HINT = "Is n8n running and is the workflow 'Payment paid to order' active (Publish)?"


def test_paid_payment_becomes_exactly_one_order():
    pid, email = new_payment(plan="yearly")
    pay(pid, "pay")
    assert wait_for_orders(pid, 1) == 1, "No order appeared. " + HINT
    row = db(f"SELECT plan, email, vat_rule, status, amount_excl_cents, vat_cents FROM orders WHERE payment_id='{pid}'")[0].split("\t")
    assert row == ["yearly", email, "belgian_21", "paid", "14900", "3129"]


def test_foreign_company_order_is_stored_with_reverse_charge():
    pid, _ = new_payment(plan="yearly", country="NL", company="Firma BV", vat="NL853123456B01")
    pay(pid, "pay")
    assert wait_for_orders(pid, 1) == 1, "No order appeared. " + HINT
    row = db(f"SELECT vat_rule, vat_cents, vat_number FROM orders WHERE payment_id='{pid}'")[0].split("\t")
    assert row == ["reverse_charge", "0", "NL853123456B01"]


def test_the_same_webhook_again_does_not_create_a_second_order():
    pid, _ = new_payment()
    pay(pid, "pay")
    assert wait_for_orders(pid, 1) == 1, "No order appeared. " + HINT
    assert post_webhook(pid) == 200
    time.sleep(4)
    assert order_count(pid) == 1


def test_webhook_delivered_twice_creates_one_order():
    pid, _ = new_payment()
    pay(pid, "pay", twice=True)
    assert wait_for_orders(pid, 1) == 1, "No order appeared. " + HINT
    time.sleep(4)
    assert order_count(pid) == 1


@pytest.mark.parametrize("action", ["fail", "cancel"])
def test_unpaid_payments_create_no_order(action):
    pid, _ = new_payment()
    pay(pid, action)
    time.sleep(5)
    assert order_count(pid) == 0


def test_a_webhook_for_an_unknown_payment_creates_nothing():
    pid = "tr_test_deadbeef0000"
    assert post_webhook(pid) == 200        # n8n answers at once; the workflow then fails and sends an alert
    time.sleep(5)
    assert order_count(pid) == 0


def test_an_amount_that_does_not_add_up_creates_no_order():
    pid, _ = new_payment()
    db(f"UPDATE payments SET amount_cents = amount_cents + 100 WHERE id='{pid}'")
    pay(pid, "pay")
    time.sleep(6)
    assert api_payment(pid)[1]["status"] == "paid"      # the provider took the money ...
    assert order_count(pid) == 0                         # ... but we refuse to book it, and an alert goes out
