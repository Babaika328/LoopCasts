"""Members area: access after payment, setting and resetting a password, login, and the protections around them.
Needs only the site and the database (no n8n). Test members use emails that start with pytest+ and are removed afterwards."""
import hashlib
import uuid

from conftest import db, get_csrf, grant, insert_order, new_jar, scalar, site

GOOD = "a long enough password"
WRONG = "definitely not the password"


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


def insert_reset_token(email, purpose="reset", hours=2):
    """A link whose secret the test knows, so the link flow can be tried without reading email."""
    plain = uuid.uuid4().hex + uuid.uuid4().hex
    member = scalar(f"SELECT id FROM members WHERE email='{email}'")
    db(f"UPDATE password_tokens SET used_at = NOW() WHERE member_id = {member} AND used_at IS NULL")
    db("INSERT INTO password_tokens (member_id, token_hash, purpose, expires_at) "
       f"VALUES ({member}, '{hashlib.sha256(plain.encode()).hexdigest()}', '{purpose}', DATE_ADD(NOW(), INTERVAL {hours} HOUR))")
    return plain


# --- the API that n8n calls -------------------------------------------------------------------------------------

def test_the_api_needs_the_key():
    assert grant(1, key=None)[0] == 401
    assert grant(1, key="not-the-key")[0] == 401


def test_the_api_refuses_unknown_orders_and_bad_input():
    assert grant(999999999)[0] == 404
    assert site("POST", "/members/api/create.php", {"order_id": "abc"}, {"Authorization": "Bearer test_local_members"})[0] == 400


def test_a_new_customer_gets_one_link_and_a_subscription():
    order_id, email = insert_order("yearly")
    status, answer = grant(order_id)
    assert status == 200 and answer["needs_password"] is True and answer["setup_url"].startswith("http")
    assert scalar(f"SELECT access_until = DATE_ADD(CURDATE(), INTERVAL 1 YEAR) FROM members WHERE email='{email}'") == "1"
    assert scalar(f"SELECT password_hash IS NULL FROM members WHERE email='{email}'") == "1"


def test_repeating_the_call_for_the_same_order_changes_nothing():
    order_id, email = insert_order("monthly")
    first = grant(order_id)[1]
    until = scalar(f"SELECT access_until FROM members WHERE email='{email}'")
    second = grant(order_id)[1]
    assert second["already_granted"] is True and second["setup_url"] is None
    assert scalar(f"SELECT access_until FROM members WHERE email='{email}'") == until
    assert first["setup_url"]


def test_a_renewal_extends_access_and_sends_no_new_link():
    email, _ = new_member("monthly")
    before = scalar(f"SELECT access_until FROM members WHERE email='{email}'")
    order_id, _ = insert_order("monthly", email=email)
    status, answer = grant(order_id)
    assert status == 200 and answer["needs_password"] is False and answer["setup_url"] is None
    assert scalar(f"SELECT DATE_ADD('{before}', INTERVAL 1 MONTH) = access_until FROM members WHERE email='{email}'") == "1"


def test_a_single_course_gives_an_account_but_no_subscription():
    email, _ = new_member("single", course="n8n basics")
    assert scalar(f"SELECT access_until IS NULL FROM members WHERE email='{email}'") == "1"
    (status, _, _), jar = login(email, GOOD)
    status, _, body = site("GET", "/members/", jar=jar)
    assert status == 200 and "no active subscription" in body and "n8n basics" in body


# --- choosing a password ----------------------------------------------------------------------------------------

def test_the_full_path_from_payment_to_logged_in():
    order_id, email = insert_order("yearly", name="Eva Janssens")
    token = token_from(grant(order_id)[1]["setup_url"])

    status, headers, body = site("GET", f"/members/set-password.php?token={token}")
    assert status == 200 and "Choose your password" in body
    assert headers.get("referrer-policy") == "no-referrer" and "no-store" in headers.get("cache-control", "")

    assert "at least 10" in set_password(token, "short")[2]
    assert "not the same" in set_password(token, GOOD, again="something else entirely")[2]

    status, headers, _ = set_password(token, GOOD)
    assert status == 302 and "notice=password-set" in headers["location"]

    (status, headers, _), jar = login(email, GOOD)
    assert status == 302 and headers["location"] == "/members/"
    status, _, body = site("GET", "/members/", jar=jar)
    assert status == 200 and "Hello, Eva Janssens" in body and "active until" in body

    csrf = get_csrf("/members/", jar)
    assert site("POST", "/members/logout.php", {"csrf": csrf}, jar=jar)[0] == 302
    assert site("GET", "/members/", jar=jar)[0] == 302            # logged out: back to the login page


def test_a_link_works_only_once():
    order_id, email = insert_order()
    token = token_from(grant(order_id)[1]["setup_url"])
    assert set_password(token, GOOD)[0] == 302
    assert "no longer works" in site("GET", f"/members/set-password.php?token={token}")[2]
    # Trying to use the used link again (with a valid form token) is refused and the password stays as it was.
    jar = new_jar()
    csrf = get_csrf("/members/login.php", jar)
    status, _, body = site("POST", "/members/set-password.php", {"csrf": csrf, "token": token, "password": "another long password",
                                                                  "password_again": "another long password"}, jar=jar)
    assert status == 200 and "no longer works" in body
    assert login(email, GOOD)[0][0] == 302


def test_an_expired_link_is_refused():
    order_id, email = insert_order()
    token = token_from(grant(order_id)[1]["setup_url"])
    db(f"UPDATE password_tokens SET expires_at = NOW() - INTERVAL 1 HOUR WHERE member_id = (SELECT id FROM members WHERE email='{email}')")
    assert "no longer works" in site("GET", f"/members/set-password.php?token={token}")[2]


def test_made_up_links_are_refused_without_errors():
    for token in (uuid.uuid4().hex + uuid.uuid4().hex, "abc", ""):
        status, _, body = site("GET", f"/members/set-password.php?token={token}")
        assert status == 200 and "no longer works" in body


def test_the_password_is_stored_as_a_bcrypt_hash():
    email, _ = new_member()
    assert scalar(f"SELECT LEFT(password_hash, 4) FROM members WHERE email='{email}'") == "$2y$"
    assert scalar(f"SELECT CHAR_LENGTH(password_hash) FROM members WHERE email='{email}'") == "60"


# --- logging in -------------------------------------------------------------------------------------------------

def test_the_account_page_needs_a_login():
    status, headers, _ = site("GET", "/members/")
    assert status == 302 and headers["location"] == "/members/login.php"


def test_a_wrong_password_and_an_unknown_email_look_the_same():
    email, _ = new_member()
    (s1, _, b1), _ = login(email, WRONG)
    (s2, _, b2), _ = login(f"nobody-{uuid.uuid4().hex[:6]}@example.test", WRONG)
    assert s1 == s2 == 200 and "Wrong email or password." in b1 and "Wrong email or password." in b2


def test_a_member_who_has_not_chosen_a_password_cannot_log_in():
    order_id, email = insert_order()
    grant(order_id)
    (status, _, body), _ = login(email, "")
    assert status == 200 and "Wrong email or password." in body


def test_login_is_slowed_down_after_five_failures():
    email, _ = new_member()
    for _ in range(5):
        login(email, WRONG)
    (status, _, body), _ = login(email, GOOD)             # even the right password is refused for a while
    assert status == 429 and "Too many attempts" in body


def test_login_without_the_csrf_token_is_refused():
    email, _ = new_member()
    jar = new_jar()
    status, _, _ = site("POST", "/members/login.php", {"email": email, "password": GOOD}, jar=jar)
    assert status == 400
    assert site("GET", "/members/", jar=jar)[0] == 302


def test_the_session_changes_at_login_and_the_cookie_is_protected():
    email, _ = new_member()
    jar = new_jar()
    status, first, body = site("GET", "/members/login.php", jar=jar)
    cookie_before = first["set-cookie"].split(";")[0]
    csrf = __import__("conftest").csrf_from(body)
    status, after, _ = site("POST", "/members/login.php", {"csrf": csrf, "email": email, "password": GOOD}, jar=jar)
    assert status == 302
    assert after["set-cookie"].split(";")[0] != cookie_before, "The session id must change at login (session fixation)"
    assert "HttpOnly" in after["set-cookie"] and "SameSite=Lax" in after["set-cookie"]


def test_an_ended_subscription_is_shown_as_ended():
    email, _ = new_member()
    db(f"UPDATE members SET access_until = CURDATE() - INTERVAL 1 DAY WHERE email='{email}'")
    (status, _, _), jar = login(email, GOOD)
    body = site("GET", "/members/", jar=jar)[2]
    assert "subscription ended on" in body and "active until" not in body


# --- forgotten passwords ----------------------------------------------------------------------------------------

def test_the_forgot_page_gives_the_same_answer_for_everyone():
    email, _ = new_member()
    unknown = f"{'pytest+'}nobody{uuid.uuid4().hex[:6]}@example.test"
    answers = []
    for address in (email, unknown):
        jar = new_jar()
        csrf = get_csrf("/members/forgot.php", jar)
        status, _, body = site("POST", "/members/forgot.php", {"csrf": csrf, "email": address}, jar=jar)
        answers.append((status, "If this address belongs to a member" in body))
    assert answers[0] == answers[1] == (200, True)
    assert scalar(f"SELECT COUNT(*) FROM password_tokens WHERE purpose='reset' AND member_id=(SELECT id FROM members WHERE email='{email}')") == "1"
    assert scalar(f"SELECT COUNT(*) FROM members WHERE email='{unknown}'") == "0"      # asking never creates an account


def test_a_reset_link_changes_the_password():
    email, _ = new_member()
    plain = insert_reset_token(email)
    status, headers, _ = set_password(plain, "a brand new long password")
    assert status == 302
    (status, _, body), _ = login(email, GOOD)
    assert "Wrong email or password." in body                                       # the old password no longer works
    (status, headers, _), _ = login(email, "a brand new long password")
    assert status == 302 and headers["location"] == "/members/"


def test_a_new_reset_link_cancels_the_older_one():
    email, _ = new_member()
    old = insert_reset_token(email)
    insert_reset_token(email)
    assert "no longer works" in site("GET", f"/members/set-password.php?token={old}")[2]