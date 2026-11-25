"""Helpers shared by the members, password and security tests."""
import hashlib
import uuid

from conftest import db, get_csrf, grant, insert_order, new_jar, scalar, site

GOOD = "Correct-Horse-9"            # meets the password rules
WRONG = "Definitely-Not-1!"


def token_from(setup_url):
    return setup_url.split("token=")[1]


def set_password(token, password, again=None, jar=None):
    jar = jar or new_jar()
    csrf = get_csrf(f"/members/set-password.php?token={token}", jar)
    data = {"csrf": csrf, "token": token, "password": password, "password_again": password if again is None else again}
    return site("POST", "/members/set-password.php", data, jar=jar)


def login(email, password, jar=None):
    jar = jar or new_jar()
    csrf = get_csrf("/members/login.php", jar)
    return site("POST", "/members/login.php", {"csrf": csrf, "email": email, "password": password}, jar=jar), jar


def new_member(plan="yearly", course=None, password=GOOD):
    """A paid order, access granted through the API, and a password chosen through the link. Returns (email, order id)."""
    order_id, email = insert_order(plan, course)
    status, answer = grant(order_id)
    assert status == 200 and answer["setup_url"], answer
    status, headers, _ = set_password(token_from(answer["setup_url"]), password)
    assert status == 302, "Setting the first password failed"
    return email, order_id


def logged_in_member(plan="yearly", password=GOOD):
    """A member who is logged in. Returns (email, cookie jar)."""
    email, _ = new_member(plan, password=password)
    (status, _, _), jar = login(email, password)
    assert status == 302
    return email, jar


def insert_reset_token(email, purpose="reset", hours=2):
    """A link whose secret the test knows, so the link flow can be tried without reading email."""
    plain = uuid.uuid4().hex + uuid.uuid4().hex
    member = scalar(f"SELECT id FROM members WHERE email='{email}'")
    db(f"UPDATE password_tokens SET used_at = NOW() WHERE member_id = {member} AND used_at IS NULL")
    db("INSERT INTO password_tokens (member_id, token_hash, purpose, expires_at) "
       f"VALUES ({member}, '{hashlib.sha256(plain.encode()).hexdigest()}', '{purpose}', DATE_ADD(NOW(), INTERVAL {hours} HOUR))")
    return plain


def member_for_order(order_id, email, password=GOOD):
    """Give the customer of an existing order access, choose the password, log in. Returns the cookie jar."""
    status, answer = grant(order_id)
    assert status == 200 and answer["setup_url"], answer
    assert set_password(token_from(answer["setup_url"]), password)[0] == 302
    (status, _, _), jar = login(email, password)
    assert status == 302
    return jar


def invoice_number_for(order_id):
    """Create the invoice of an order in the test year 9999 (so the real counter is untouched). Returns its number."""
    return db(f"CALL create_invoice({order_id}, 9999)")[-1]