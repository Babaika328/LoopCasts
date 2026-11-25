"""The member profile: invoices, data download, cancel and delete requests, renewal, prefilled order page."""
import json
import re

import pytest

from conftest import db, get_csrf, insert_order, new_jar, scalar, site
from members_helpers import GOOD, WRONG, invoice_number_for, login, logged_in_member, member_for_order, new_member

pytestmark = pytest.mark.usefixtures("fresh_limits")


def member_with_invoice(**order):
    order_id, email = insert_order(**order)
    jar = member_for_order(order_id, email)
    return email, jar, invoice_number_for(order_id)


def profile_post(jar, **data):
    return site("POST", "/members/profile.php", {"csrf": get_csrf("/members/profile.php", jar), **data}, jar=jar)


# --- invoices -----------------------------------------------------------------------------------------------------

def test_the_invoice_page_needs_a_login():
    status, headers, _ = site("GET", "/members/invoice.php?n=9999-0001")
    assert status == 302 and headers["location"] == "/members/login.php"


def test_a_member_sees_their_own_invoice_with_the_right_amounts():
    email, jar, number = member_with_invoice(plan="yearly")
    status, _, body = site("GET", f"/members/invoice.php?n={number}", jar=jar)
    assert status == 200 and f"Invoice {number}" in body
    assert "€ 149,00" in body and "VAT 21%" in body and "€ 31,29" in body and "€ 180,29" in body
    assert "LoopCasts BV" in body and "Fietsstraat 12 bus 2" in body and "Yearly subscription LoopCasts" in body


def test_a_reverse_charge_invoice_says_so_and_shows_the_vat_number():
    email, jar, number = member_with_invoice(plan="yearly", company="Firma BV", vat_number="NL853123456B01", country="NL",
                                             vat_cents=0, vat_rule="reverse_charge")
    body = site("GET", f"/members/invoice.php?n={number}", jar=jar)[2]
    assert "VAT 0% (VAT reverse charged)" in body and "NL853123456B01" in body and "€ 149,00" in body and "Firma BV" in body


def test_a_single_course_invoice_names_the_course():
    email, jar, number = member_with_invoice(plan="single", course="Cron and schedulers")
    assert "Single course: Cron and schedulers" in site("GET", f"/members/invoice.php?n={number}", jar=jar)[2]


def test_someone_elses_invoice_looks_exactly_like_one_that_does_not_exist():
    owner, owner_jar, number = member_with_invoice()
    other_email, other_jar = logged_in_member()
    stranger = site("GET", f"/members/invoice.php?n={number}", jar=other_jar)
    missing = site("GET", "/members/invoice.php?n=9999-4321", jar=other_jar)
    assert stranger[0] == missing[0] == 404
    assert number not in stranger[2] and "Invoice not found" in stranger[2]


@pytest.mark.parametrize("number", ["abc", "9999-0001' OR '1'='1", "9999-1", "../../etc/passwd", ""])
def test_a_badly_formed_invoice_number_is_just_not_found(number):
    email, jar = logged_in_member()
    assert site("GET", "/members/invoice.php?n=" + number.replace(" ", "%20").replace("'", "%27"), jar=jar)[0] == 404


def test_the_customer_name_is_escaped_on_the_invoice():
    email, jar, number = member_with_invoice(name="<b>Eva</b> & Co")
    body = site("GET", f"/members/invoice.php?n={number}", jar=jar)[2]
    assert "&lt;b&gt;Eva&lt;/b&gt; &amp; Co" in body and "<b>Eva</b>" not in body


def test_the_account_page_links_to_the_invoice_and_to_the_profile():
    email, jar, number = member_with_invoice()
    body = site("GET", "/members/", jar=jar)[2]
    assert f'href="/members/invoice.php?n={number}"' in body and 'href="/members/profile.php"' in body


def test_the_print_script_exists_and_the_invoice_page_has_no_inline_script():
    assert site("GET", "/print.js")[0] == 200
    email, jar, number = member_with_invoice()
    body = site("GET", f"/members/invoice.php?n={number}", jar=jar)[2]
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", body) and not re.search(r"\sstyle=", body)


# --- renewing -----------------------------------------------------------------------------------------------------

def test_a_subscription_that_ends_soon_offers_renewal_with_the_same_plan():
    email, jar, _ = member_with_invoice(plan="monthly")
    db(f"UPDATE members SET access_until = CURDATE() + INTERVAL 10 DAY WHERE email='{email}'")
    assert 'href="/order.php?plan=monthly"' in site("GET", "/members/", jar=jar)[2]


def test_an_ended_subscription_is_red_and_offers_renewal():
    email, jar, _ = member_with_invoice(plan="yearly")
    db(f"UPDATE members SET access_until = CURDATE() - INTERVAL 3 DAY WHERE email='{email}'")
    body = site("GET", "/members/", jar=jar)[2]
    assert "notice-error" in body and "subscription ended on" in body and 'href="/order.php?plan=yearly"' in body


def test_a_subscription_far_from_its_end_shows_no_renew_button():
    email, jar, _ = member_with_invoice(plan="yearly")
    assert "Renew your subscription" not in site("GET", "/members/", jar=jar)[2]


def test_the_order_page_is_filled_in_for_a_logged_in_member_and_not_for_a_visitor():
    email, jar = logged_in_member()
    assert f'value="{email}"' in site("GET", "/order.php?plan=yearly", jar=jar)[2]
    status, headers, body = site("GET", "/order.php?plan=yearly")
    assert f'value="{email}"' not in body and "set-cookie" not in headers      # a visitor gets neither the data nor a cookie


# --- the data download ---------------------------------------------------------------------------------------------

def test_the_data_download_needs_a_login():
    assert site("GET", "/members/data.php")[0] == 302


def test_the_data_download_has_my_data_and_never_the_password_hash():
    email, jar, number = member_with_invoice(plan="yearly", name="Eva Janssens")
    status, headers, body = site("GET", "/members/data.php", jar=jar)
    assert status == 200 and "attachment" in headers["content-disposition"]
    data = json.loads(body)
    assert data["profile"]["email"] == email and data["profile"]["name"] == "Eva Janssens"
    assert data["orders"][0]["invoice_number"] == number and data["orders"][0]["plan"] == "yearly"
    assert "password" not in body.lower() and "$2y$" not in body
    assert scalar(f"SELECT COUNT(*) FROM audit_log WHERE action='data_export' AND actor_email='{email}'") == "1"   # the export is logged


def test_the_download_holds_only_my_own_orders():
    mine, jar, _ = member_with_invoice()
    other, _, _ = member_with_invoice()
    body = site("GET", "/members/data.php", jar=jar)[2]
    assert other not in body


# --- requests to a person ------------------------------------------------------------------------------------------

def test_the_profile_page_needs_a_login():
    assert site("GET", "/members/profile.php")[0] == 302


def test_a_cancel_request_becomes_one_ticket_for_a_person():
    email, jar, _ = member_with_invoice()
    status, _, body = profile_post(jar, action="cancel", reason="I changed jobs")
    assert status == 200 and "We received your request" in body and "decided by a person" in body
    row = db(f"SELECT category, status, source, body FROM tickets WHERE from_email='{email}'")
    assert row == ["cancel_or_refund\tneeds_human\tprofile\tI changed jobs"]
    assert "already have your request" in profile_post(jar, action="cancel", reason="again")[2]
    assert scalar(f"SELECT COUNT(*) FROM tickets WHERE from_email='{email}'") == "1"       # asking twice does not make a second ticket


def test_cancelling_is_not_offered_to_someone_without_a_subscription():
    order_id, email = insert_order(plan="single", course="n8n basics")
    jar = member_for_order(order_id, email)
    body = site("GET", "/members/profile.php", jar=jar)[2]
    assert "You have no subscription." in body
    assert "no subscription to cancel" in profile_post(jar, action="cancel")[2]
    assert scalar(f"SELECT COUNT(*) FROM tickets WHERE from_email='{email}'") == "0"


def test_deleting_the_account_needs_the_password():
    email, jar, _ = member_with_invoice()
    status, _, body = profile_post(jar, action="delete", password=WRONG)
    assert status == 200 and "password is not right" in body and "notice-error" in body
    assert scalar(f"SELECT COUNT(*) FROM tickets WHERE from_email='{email}'") == "0"
    assert "We received your request" in profile_post(jar, action="delete", password=GOOD)[2]
    assert db(f"SELECT category, status FROM tickets WHERE from_email='{email}'") == ["privacy_request\tneeds_human"]


def test_guessing_the_password_on_the_delete_form_is_slowed_down():
    email, jar, _ = member_with_invoice()
    for _ in range(5):
        profile_post(jar, action="delete", password=WRONG)
    status, _, body = profile_post(jar, action="delete", password=GOOD)
    assert status == 429 and "Too many attempts" in body


def test_the_requests_are_listed_for_the_member_who_made_them():
    email, jar, _ = member_with_invoice()
    profile_post(jar, action="cancel", reason="x")
    assert "Cancel subscription request" in site("GET", "/members/profile.php", jar=jar)[2]
    other, other_jar = logged_in_member()
    assert "Cancel subscription request" not in site("GET", "/members/profile.php", jar=other_jar)[2]


def test_the_profile_forms_need_the_csrf_token():
    email, jar, _ = member_with_invoice()
    assert site("POST", "/members/profile.php", {"action": "cancel", "reason": "x"}, jar=jar)[0] == 400
    assert scalar(f"SELECT COUNT(*) FROM tickets WHERE from_email='{email}'") == "0"


def test_a_reason_with_html_is_stored_as_text_and_never_run():
    email, jar, _ = member_with_invoice()
    profile_post(jar, action="cancel", reason="<script>alert(1)</script>")
    assert scalar(f"SELECT body FROM tickets WHERE from_email='{email}'") == "<script>alert(1)</script>"
    assert "<script>alert(1)</script>" not in site("GET", "/members/profile.php", jar=jar)[2]