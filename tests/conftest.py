"""Shared helpers for the LoopCasts tests. They run against the real local stack (DDEV + n8n)."""
import json
import os
import re
import shlex
import subprocess
import time
import urllib.parse
import urllib.request
import uuid

import pytest

API_KEY = os.environ.get("SIM_API_KEY", "test_local_simulator")   # the simulator's test key, not a real secret
N8N_URL = os.environ.get("N8N_URL", "http://localhost:5678")
MARK = "pytest+"        # every test customer's email starts with this, so clean-up can find the rows
PAYMENT_ID = re.compile(r"^tr_test_[0-9a-f]+$")


def _run(args, timeout=60):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def _parse_http(raw):
    raw = raw.replace("\r\n", "\n")
    assert raw.strip(), "No answer from the site. Is DDEV running? Try: bash start.sh"
    head, _, body = raw.partition("\n\n")
    while head.startswith("HTTP/") and " 100 " in head.split("\n")[0] and body:   # skip interim answers
        head, _, body = body.partition("\n\n")
    lines = head.split("\n")
    status = int(lines[0].split()[1])
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    return status, headers, body


def site(method, path, data=None, headers=None, jar=None):
    """Call the site from inside the DDEV web container, so DNS and ports do not matter. `jar` keeps cookies between calls."""
    cmd = ["curl", "-s", "-i", "-X", method, "http://localhost" + path]
    if jar:
        cmd += ["-c", jar, "-b", jar]
    for key, value in (headers or {}).items():
        cmd += ["-H", f"{key}: {value}"]
    if data is not None:
        cmd += ["--data", urllib.parse.urlencode(data)]
    return _parse_http(_run(["ddev", "exec", shlex.join(cmd)]).stdout)


def db(sql):
    """Run SQL in the DDEV database. Returns the output lines (tab separated)."""
    result = _run(["ddev", "mysql", "-N", "-B", "-e", sql])
    assert result.returncode == 0, f"SQL failed: {result.stderr}"
    return [line for line in result.stdout.splitlines() if line.strip()]


def scalar(sql):
    return db(sql)[-1]


def new_jar():
    return "/tmp/pytest-jar-" + uuid.uuid4().hex[:10]


def csrf_from(body):
    found = re.search(r'name="csrf" value="([0-9a-f]+)"', body)
    assert found, "No csrf field on the page"
    return found.group(1)


def get_csrf(path, jar):
    status, _, body = site("GET", path, jar=jar)
    return csrf_from(body)


def insert_order(plan="yearly", course=None, email=None, name="Test Member"):
    """Insert a paid order straight into the database (as n8n would). Returns (order id, email)."""
    email = email or f"{MARK}m{uuid.uuid4().hex[:8]}@example.test"
    course_sql = f"'{course}'" if course else "NULL"
    rows = db(
        "INSERT INTO orders (payment_id, plan, course, name, email, country, amount_excl_cents, vat_cents, vat_rule, status) "
        f"VALUES ('tr_test_{uuid.uuid4().hex[:12]}', '{plan}', {course_sql}, '{name}', '{email}', 'BE', 14900, 3129, 'belgian_21', 'invoiced'); "
        "SELECT LAST_INSERT_ID();"
    )
    return int(rows[-1]), email


def grant(order_id, key="test_local_members"):
    """Call the members API like n8n does. Returns (status, json)."""
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    status, _, body = site("POST", "/members/api/create.php", {"order_id": str(order_id)}, headers)
    return status, (json.loads(body) if body.lstrip().startswith("{") else None)


def place_order(plan="yearly", country="BE", company=None, vat=None, course="n8n basics", email=None, name="Test Customer"):
    """Submit the order form. Returns (status, headers, body, email)."""
    email = email or f"{MARK}{uuid.uuid4().hex[:8]}@example.test"
    data = {"plan": plan, "name": name, "email": email, "country": country}
    if plan == "single":
        data["course"] = course
    if company is not None:
        data.update({"is_company": "1", "company": company, "vat": vat or ""})
    status, headers, body = site("POST", "/order.php", data)
    return status, headers, body, email


def payment_id_from(headers):
    location = headers.get("location", "")
    assert "id=" in location, f"The order form did not redirect to the checkout (Location: {location!r})"
    pid = location.split("id=")[-1]
    assert PAYMENT_ID.match(pid), f"Odd payment id: {pid!r}"
    return pid


def new_payment(**kwargs):
    status, headers, _, email = place_order(**kwargs)
    assert status == 302, f"Expected a redirect to the checkout, got HTTP {status}"
    return payment_id_from(headers), email


def pay(pid, action="pay", twice=False):
    data = {"id": pid, "action": action}
    if twice:
        data["twice"] = "1"
    status, _, body = site("POST", "/pay/checkout.php", data)
    assert status == 200
    return body


def api_payment(pid, key=API_KEY):
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    status, _, body = site("GET", f"/pay/api.php?id={pid}", headers=headers)
    return status, (json.loads(body) if body.lstrip().startswith("{") else None)


def post_webhook(pid):
    """Send the provider's webhook straight to n8n: a form-encoded POST with only the payment id."""
    request = urllib.request.Request(
        N8N_URL + "/webhook/payment",
        data=urllib.parse.urlencode({"id": pid}).encode(),
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status


def order_count(pid):
    assert PAYMENT_ID.match(pid) or pid.startswith("tr_test_"), pid
    return int(scalar(f"SELECT COUNT(*) FROM orders WHERE payment_id='{pid}'"))


def wait_for_orders(pid, expected, timeout=20):
    """Wait until the number of orders for a payment equals `expected`. Returns the last count."""
    deadline = time.time() + timeout
    count = order_count(pid)
    while count != expected and time.time() < deadline:
        time.sleep(1)
        count = order_count(pid)
    return count


def mailpit_subjects():
    """Subjects of the latest mails in Mailpit (DDEV's mail catcher), newest first. Skips the test if Mailpit cannot be asked."""
    result = _run(["ddev", "exec", shlex.join(["curl", "-s", "http://localhost:8025/api/v1/messages?limit=200"])])
    try:
        messages = json.loads(result.stdout)["messages"]
        return [str(m.get("Subject") or m.get("subject") or "") for m in messages]
    except (ValueError, KeyError, TypeError, AttributeError):
        pytest.skip("Mailpit could not be asked (check the port with: ddev describe)")


def mailpit_json(path):
    result = _run(["ddev", "exec", shlex.join(["curl", "-s", "http://localhost:8025" + path])])
    try:
        return json.loads(result.stdout)
    except ValueError:
        pytest.skip("Mailpit could not be asked (check the port with: ddev describe)")


def mails_to(address):
    """Mails in Mailpit that are addressed to `address`, as a list of {"subject", "text", "html"}."""
    data = mailpit_json("/api/v1/messages?limit=200")
    if "messages" not in data:
        pytest.skip("Mailpit answered in a shape the tests do not know")
    found = []
    for message in data["messages"]:
        recipients = [str(t.get("Address", "")).lower() for t in (message.get("To") or [])]
        if address.lower() in recipients:
            detail = mailpit_json("/api/v1/message/" + str(message["ID"]))
            found.append({"subject": str(message.get("Subject", "")), "text": str(detail.get("Text", "")), "html": str(detail.get("HTML", ""))})
    return found


def wait_for_mail(address, subject_part, timeout=25):
    """Wait until a mail with `subject_part` in its subject has arrived for `address`. Returns the matching mails."""
    deadline = time.time() + timeout
    while True:
        mails = [m for m in mails_to(address) if subject_part in m["subject"]]
        if mails or time.time() > deadline:
            return mails
        time.sleep(1)


def mailpit_count(text):
    """How many of the latest mails have `text` in their subject."""
    return sum(1 for subject in mailpit_subjects() if text in subject)


@pytest.fixture(scope="session", autouse=True)
def clean_up_test_data():
    yield
    db(f"DELETE i FROM invoices i JOIN orders o ON o.id = i.order_id WHERE o.email LIKE '{MARK}%'")
    db(f"DELETE FROM orders WHERE email LIKE '{MARK}%'")
    db(f"DELETE FROM payments WHERE metadata LIKE '%{MARK}%'")
    db("DELETE FROM login_attempts")          # development database: no real attempts to keep
    db(f"DELETE FROM members WHERE email LIKE '{MARK}%'")
    _run(["ddev", "exec", "rm -f /tmp/pytest-jar-*"])
    db("DELETE FROM invoice_counters WHERE year = 9999")
    # Test orders may have used real numbers of this year. Give the counter back, so the real numbers stay gap-free.
    db("UPDATE invoice_counters c SET c.last_number = ("
       "SELECT COALESCE(MAX(CAST(SUBSTRING(invoice_number, 6) AS UNSIGNED)), 0) FROM invoices "
       "WHERE invoice_number LIKE CONCAT(c.year, '-%'))")


@pytest.fixture
def fresh_limits():
    """Start a test with empty rate-limit counters, so one test's failed logins never block the next."""
    db("DELETE FROM login_attempts")
    yield