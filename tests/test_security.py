"""Security checks: headers, CSRF, rate limits, password rules, injection attempts, session handling, exposed files."""
import re
import time
import uuid

import pytest

from conftest import MARK, db, get_csrf, grant, insert_order, new_jar, place_order, scalar, site, _run
from members_helpers import (GOOD, insert_reset_token, logged_in_member, login, new_member, set_password)

pytestmark = pytest.mark.usefixtures("fresh_limits")


# --- headers and content -----------------------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/order.php", "/members/login.php", "/members/forgot.php", "/pay/checkout.php?id=tr_test_000000000000"])
def test_php_pages_send_the_security_headers(path):
    headers = site("GET", path)[1]
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
    csp = headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp and "script-src 'self'" in csp


def test_pages_use_no_inline_script_or_style_so_the_policy_can_stay_strict():
    pid, _ = new_payment_for_pages()
    paths = ["/order.php", "/order.php?plan=single", "/members/login.php", "/members/forgot.php",
             "/members/set-password.php?token=abc", f"/pay/checkout.php?id={pid}", f"/order-done.php?id={pid}"]
    email, jar = logged_in_member()
    for path in paths + ["/members/", "/members/password.php"]:
        body = site("GET", path, jar=jar if path.startswith("/members/") and path not in ("/members/login.php", "/members/forgot.php") and "set-password" not in path else None)[2]
        assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", body), f"inline script on {path}"
        assert not re.search(r"\sstyle=", body) and "<style" not in body, f"inline style on {path}"


def new_payment_for_pages():
    from conftest import new_payment
    return new_payment()


def test_code_and_secrets_are_not_served_to_visitors():
    assert "<?php" not in site("GET", "/lib/members.php")[2] and "password_hash" not in site("GET", "/lib/members.php")[2]
    for path in ["/.env", "/.git/config", "/db/schema.sql", "/n8n/docker-compose.yml", "/tests/conftest.py"]:
        assert site("GET", path)[0] in (403, 404), path          # DDEV answers 403 for dot files, 404 for the rest


def test_the_members_api_accepts_only_post():
    status, _, _ = site("GET", "/members/api/create.php", headers={"Authorization": "Bearer test_local_members"})
    assert status == 405


# --- CSRF --------------------------------------------------------------------------------------------------------

def test_every_form_refuses_a_post_without_the_csrf_token():
    assert site("POST", "/members/forgot.php", {"email": "x@example.test"}, jar=new_jar())[0] == 400
    assert site("POST", "/members/login.php", {"email": "x@example.test", "password": "x"}, jar=new_jar())[0] == 400

    order_id, email = insert_order()
    token = grant(order_id)[1]["setup_url"].split("token=")[1]
    status, _, _ = site("POST", "/members/set-password.php", {"token": token, "password": GOOD, "password_again": GOOD}, jar=new_jar())
    assert status == 400
    assert login(email, GOOD)[0][0] == 200                  # the password was not set


def test_logging_out_needs_the_csrf_token():
    email, jar = logged_in_member()
    site("POST", "/members/logout.php", {}, jar=jar)
    assert site("GET", "/members/", jar=jar)[0] == 200      # still logged in


# --- rate limits -------------------------------------------------------------------------------------------------

def test_forgot_password_requests_are_limited_per_address():
    jar = new_jar()
    csrf = get_csrf("/members/forgot.php", jar)
    address = f"{MARK}limit{uuid.uuid4().hex[:6]}@example.test"
    statuses = [site("POST", "/members/forgot.php", {"csrf": csrf, "email": address}, jar=jar)[0] for _ in range(6)]
    assert statuses == [200] * 5 + [429]


def test_the_order_form_is_limited_per_address():
    assert place_order()[0] == 302
    ip = scalar("SELECT ip FROM login_attempts WHERE email LIKE 'order:%' ORDER BY id DESC LIMIT 1")
    db(f"INSERT INTO login_attempts (email, ip) SELECT 'order:{ip}', '{ip}' FROM seq_1_to_119")
    status, _, body, _ = place_order()
    assert status == 429 and "Too many orders" in body


def test_order_attempts_do_not_block_logging_in():
    email, _ = new_member()
    assert place_order()[0] == 302
    ip = scalar("SELECT ip FROM login_attempts WHERE email LIKE 'order:%' ORDER BY id DESC LIMIT 1")
    db(f"INSERT INTO login_attempts (email, ip) SELECT 'order:{ip}', '{ip}' FROM seq_1_to_119")
    assert login(email, GOOD)[0][0] == 302


# --- password rules ----------------------------------------------------------------------------------------------

def test_the_password_rules():
    email, _ = new_member()
    local = email.split("@")[0]
    cases = [
        ("Sh0rt!", "at least 8 characters"),
        ("alllowercase1!", "an uppercase letter"),
        ("ALLUPPERCASE1!", "a lowercase letter"),
        ("NoDigitsHere!", "a digit"),
        ("NoSpecial123", "a special character"),
        ("A1!" + "a" * 70, "at most 72 characters"),
        ("Password1!", "too common"),
        ("Loopcasts2019!", "too common"),
        (local + "Ab1!", "must not contain the first part of your email"),
        ("abc", "at least 8 characters"),
    ]
    for password, expected in cases:
        status, _, body = set_password(insert_reset_token(email), password)
        assert status == 200 and expected in body, (password, expected)
    for password in ["Correct-Horse-9", "Tr0ub4dor&3x", "Zomer-Zon-2026!", "Pa$$w0rd-Lang-77"]:
        assert set_password(insert_reset_token(email), password)[0] == 302, password


def test_password_errors_are_shown_in_red():
    email, _ = new_member()
    assert "notice-error" in set_password(insert_reset_token(email), "short")[2]


# --- injection attempts ------------------------------------------------------------------------------------------

PAYLOADS = ["' OR '1'='1", "admin'--", "'; DROP TABLE members;--", '" OR ""="', "1; SELECT SLEEP(5)", "' UNION SELECT password_hash FROM members--"]


def test_sql_injection_attempts_do_not_log_anyone_in_or_break_anything():
    email, _ = new_member()
    started = time.time()
    for payload in PAYLOADS:
        (status, _, body), jar = login(payload, payload)
        assert status == 200 and "Wrong email or password." in body, payload
        assert site("GET", "/members/", jar=jar)[0] == 302
        jar2 = new_jar()
        csrf = get_csrf("/members/forgot.php", jar2)
        assert site("POST", "/members/forgot.php", {"csrf": csrf, "email": payload}, jar=jar2)[0] == 200
        assert site("GET", "/members/set-password.php?token=" + payload.replace(" ", "%20"))[0] == 200
        status, headers, _, _ = place_order(email=f"{MARK}x@example.test", name=payload, company=payload, vat="NL853123456B01", country="NL")
        assert status in (200, 302)
    assert time.time() - started < 60
    assert int(scalar("SELECT COUNT(*) FROM members")) >= 1            # the table is still there
    assert scalar(f"SELECT COUNT(*) FROM members WHERE email='{email}'") == "1"


def test_a_sleep_payload_does_not_make_the_database_wait():
    started = time.time()
    login("x' OR SLEEP(6)-- ", "x")
    assert time.time() - started < 5


# --- sessions ----------------------------------------------------------------------------------------------------

def test_a_copied_session_cookie_stops_working_after_logout():
    email, jar = logged_in_member()
    copy = jar + "-copy"
    _run(["ddev", "exec", f"cp {jar} {copy}"])
    assert site("GET", "/members/", jar=copy)[0] == 200
    csrf = get_csrf("/members/", jar)
    assert site("POST", "/members/logout.php", {"csrf": csrf}, jar=jar)[0] == 302
    assert site("GET", "/members/", jar=copy)[0] == 302            # the server-side session is gone, the old cookie is useless
    assert site("GET", "/members/", jar=jar)[0] == 302


def test_account_pages_are_not_cached():
    email, jar = logged_in_member()
    headers = site("GET", "/members/", jar=jar)[1]
    assert "no-store" in headers.get("cache-control", "") and headers.get("referrer-policy") == "no-referrer"