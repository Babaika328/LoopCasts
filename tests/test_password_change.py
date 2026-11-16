"""A logged-in member changing their own password."""
import pytest

from conftest import get_csrf, site
from members_helpers import GOOD, WRONG, login, logged_in_member

pytestmark = pytest.mark.usefixtures("fresh_limits")
NEW = "Brand-New-Pass-5!"


def change(jar, current, new, again=None, csrf=True):
    data = {"current": current, "password": new, "password_again": new if again is None else again}
    if csrf:
        data["csrf"] = get_csrf("/members/password.php", jar)
    return site("POST", "/members/password.php", data, jar=jar)


def test_the_page_needs_a_login():
    status, headers, _ = site("GET", "/members/password.php")
    assert status == 302 and headers["location"] == "/members/login.php"


def test_a_wrong_current_password_is_refused():
    email, jar = logged_in_member()
    status, _, body = change(jar, WRONG, NEW)
    assert status == 200 and "current password is not right" in body and "notice-error" in body


def test_a_weak_new_password_is_refused():
    email, jar = logged_in_member()
    status, _, body = change(jar, GOOD, "weakpassword")
    assert status == 200 and "Your password needs" in body


def test_the_new_password_must_differ_and_must_match():
    email, jar = logged_in_member()
    assert "different from the current one" in change(jar, GOOD, GOOD)[2]
    assert "not the same" in change(jar, GOOD, NEW, again="Other-Pass-6!")[2]


def test_changing_the_password_works_and_the_old_one_stops_working():
    email, jar = logged_in_member()
    status, _, body = change(jar, GOOD, NEW)
    assert status == 200 and "Your password was changed" in body
    assert "Wrong email or password." in login(email, GOOD)[0][2]
    assert login(email, NEW)[0][0] == 302


def test_the_session_id_changes_when_the_password_changes():
    email, jar = logged_in_member()
    before = site("GET", "/members/password.php", jar=jar)
    csrf = get_csrf("/members/password.php", jar)
    status, headers, _ = site("POST", "/members/password.php", {"csrf": csrf, "current": GOOD, "password": NEW, "password_again": NEW}, jar=jar)
    assert status == 200 and "set-cookie" in headers


def test_guessing_the_current_password_is_slowed_down():
    email, jar = logged_in_member()
    for _ in range(5):
        change(jar, WRONG, NEW)
    status, _, body = change(jar, GOOD, NEW)               # the right password is refused for a while too
    assert status == 429 and "Too many attempts" in body


def test_changing_the_password_needs_the_csrf_token():
    email, jar = logged_in_member()
    status, _, _ = change(jar, GOOD, NEW, csrf=False)
    assert status == 400
    assert login(email, GOOD)[0][0] == 302                  # nothing changed