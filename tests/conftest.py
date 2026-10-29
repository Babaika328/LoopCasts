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


def site(method, path, data=None, headers=None):
    """Call the site from inside the DDEV web container, so DNS and ports do not matter."""
    cmd = ["curl", "-s", "-i", "-X", method, "http://localhost" + path]
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


def place_order(plan="yearly", country="BE", company=None, vat=None, course="n8n basics", email=None):
    """Submit the order form. Returns (status, headers, body, email)."""
    email = email or f"{MARK}{uuid.uuid4().hex[:8]}@example.test"
    data = {"plan": plan, "name": "Test Customer", "email": email, "country": country}
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


@pytest.fixture(scope="session", autouse=True)
def clean_up_test_data():
    yield
    db(f"DELETE i FROM invoices i JOIN orders o ON o.id = i.order_id WHERE o.email LIKE '{MARK}%'")
    db(f"DELETE FROM orders WHERE email LIKE '{MARK}%'")
    db(f"DELETE FROM payments WHERE metadata LIKE '%{MARK}%'")
    db("DELETE FROM invoice_counters WHERE year = 9999")
    # Test orders may have used real numbers of this year. Give the counter back, so the real numbers stay gap-free.
    db("UPDATE invoice_counters c SET c.last_number = ("
       "SELECT COALESCE(MAX(CAST(SUBSTRING(invoice_number, 6) AS UNSIGNED)), 0) FROM invoices "
       "WHERE invoice_number LIKE CONCAT(c.year, '-%'))")