"""The full path: form, payment, webhook, n8n, order table. Needs n8n with the workflow ACTIVE."""
import re
import time

import pytest

from conftest import (api_payment, db, get_csrf, mailpit_count, mailpit_subjects, mails_to, new_payment, order_count, pay,
                      post_webhook, scalar, site, wait_for_mail, wait_for_orders)

pytestmark = pytest.mark.n8n
HINT = "Is n8n running and is the workflow 'Payment paid to order' active (Publish)?"


def test_paid_payment_becomes_exactly_one_order():
    pid, email = new_payment(plan="yearly")
    pay(pid, "pay")
    assert wait_for_orders(pid, 1) == 1, "No order appeared. " + HINT
    row = db(f"SELECT plan, email, vat_rule, status, amount_excl_cents, vat_cents FROM orders WHERE payment_id='{pid}'")[0].split("\t")
    assert row[:3] == ["yearly", email, "belgian_21"] and row[3] in ("paid", "invoiced") and row[4:] == ["14900", "3129"]


def test_a_paid_order_gets_exactly_one_invoice_number():
    pid, _ = new_payment()
    pay(pid, "pay")
    assert wait_for_orders(pid, 1) == 1, "No order appeared. " + HINT
    sql = f"SELECT invoice_number FROM invoices WHERE order_id = (SELECT id FROM orders WHERE payment_id='{pid}')"
    deadline = time.time() + 20
    rows = db(sql)
    while not rows and time.time() < deadline:
        time.sleep(1)
        rows = db(sql)
    assert len(rows) == 1 and re.match(r"^\d{4}-\d{4}$", rows[0]), "No invoice number appeared. Did you add the invoice nodes to the workflow?"
    assert scalar(f"SELECT status FROM orders WHERE payment_id='{pid}'") == "invoiced"


def _invoice_number(pid, timeout=25):
    sql = f"SELECT invoice_number FROM invoices WHERE order_id = (SELECT id FROM orders WHERE payment_id='{pid}')"
    deadline = time.time() + timeout
    rows = db(sql)
    while not rows and time.time() < deadline:
        time.sleep(1)
        rows = db(sql)
    assert rows, "No invoice number appeared. Did you add the invoice nodes to the workflow?"
    return rows[0]


def test_the_invoice_email_is_claimed_once_the_order_is_invoiced():
    pid, _ = new_payment()
    pay(pid, "pay")
    number = _invoice_number(pid)
    deadline = time.time() + 25
    sent = scalar(f"SELECT COUNT(*) FROM invoices WHERE invoice_number='{number}' AND emailed_at IS NOT NULL")
    while sent != "1" and time.time() < deadline:
        time.sleep(1)
        sent = scalar(f"SELECT COUNT(*) FROM invoices WHERE invoice_number='{number}' AND emailed_at IS NOT NULL")
    assert sent == "1", "The invoice was never marked as emailed. Did you add the claim and email nodes?"


def test_the_customer_gets_exactly_one_invoice_email_even_if_the_webhook_comes_twice():
    pid, _ = new_payment()
    pay(pid, "pay", twice=True)
    number = _invoice_number(pid)
    time.sleep(10)
    count = mailpit_count(number)
    assert count == 1, f"Expected exactly one mail with {number} in its subject, found {count}. Latest subjects: {mailpit_subjects()[:5]}"


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
    time.sleep(6)
    assert order_count(pid) == 1
    assert int(scalar(f"SELECT COUNT(*) FROM invoices WHERE order_id = (SELECT id FROM orders WHERE payment_id='{pid}')")) <= 1


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


def _wait_for_member(email, timeout=25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if scalar(f"SELECT COUNT(*) FROM members WHERE email='{email}'") == "1":
            return True
        time.sleep(1)
    return False


def test_a_paid_order_gives_the_customer_an_account_and_one_welcome_email():
    from members_helpers import GOOD, login, set_password
    import re
    pid, email = new_payment(plan="yearly")
    pay(pid, "pay", twice=True)
    assert _wait_for_member(email), "No member appeared. Did you add the access nodes to the workflow?"
    row = db(f"SELECT password_hash IS NULL, access_until = DATE_ADD(CURDATE(), INTERVAL 1 YEAR) FROM members WHERE email='{email}'")[0].split("\t")
    assert row == ["1", "1"]                                    # no password yet, one year of access

    mails = wait_for_mail(email, "choose your password")
    assert len(mails) == 1, "The welcome email did not arrive"
    time.sleep(6)
    assert len([m for m in mails_to(email) if "choose your password" in m["subject"]]) == 1   # twice the webhook, once the email

    token = re.search(r"token=([0-9a-f]{64})", mails[0]["text"]).group(1)
    assert set_password(token, GOOD)[0] == 302
    (status, _, _), jar = login(email, GOOD)
    assert status == 302
    assert "Invoice 20" in site("GET", "/members/", jar=jar)[2]                              # the account shows the invoice


def test_a_second_paid_order_extends_access_without_another_welcome_email():
    first, email = new_payment(plan="monthly")
    pay(first, "pay")
    assert _wait_for_member(email), "No member appeared. Did you add the access nodes to the workflow?"
    until = scalar(f"SELECT access_until FROM members WHERE email='{email}'")
    mails = wait_for_mail(email, "choose your password")
    assert mails, "The welcome email did not arrive"
    from members_helpers import GOOD, set_password
    import re
    assert set_password(re.search(r"token=([0-9a-f]{64})", mails[0]["text"]).group(1), GOOD)[0] == 302   # the customer chose a password

    second, _ = new_payment(plan="monthly", email=email)
    pay(second, "pay")
    extended = f"SELECT DATE_ADD('{until}', INTERVAL 1 MONTH) = access_until FROM members WHERE email='{email}'"
    deadline = time.time() + 25
    while scalar(extended) != "1" and time.time() < deadline:
        time.sleep(1)
    assert scalar(extended) == "1", "The second order did not extend the subscription"
    time.sleep(5)
    assert len([m for m in mails_to(email) if "choose your password" in m["subject"]]) == 1