"""Invoice numbering, checked in the database itself (no n8n needed): unique, gap-free, repeatable, safe when many run at once.
It uses the test year 9999, so the real counter is never touched."""
import uuid
from concurrent.futures import ThreadPoolExecutor

from conftest import _run, db, scalar

YEAR = 9999


def make_order():
    pid = "tr_test_" + uuid.uuid4().hex[:12]
    rows = db(
        "INSERT INTO orders (payment_id, plan, name, email, country, amount_excl_cents, vat_cents, vat_rule) "
        f"VALUES ('{pid}', 'yearly', 'Invoice Test', 'pytest+inv{uuid.uuid4().hex[:6]}@example.test', 'BE', 14900, 3129, 'belgian_21'); "
        "SELECT LAST_INSERT_ID();"
    )
    return int(rows[-1])


def create_invoice(order_id):
    return db(f"CALL create_invoice({order_id}, {YEAR})")[-1]


def test_parallel_calls_give_unique_numbers_without_gaps():
    orders = [make_order() for _ in range(12)]
    with ThreadPoolExecutor(max_workers=12) as pool:        # twelve at the same moment, like twelve people at one spreadsheet
        numbers = list(pool.map(create_invoice, orders))
    assert len(set(numbers)) == 12, f"duplicate numbers: {sorted(numbers)}"
    assert sorted(numbers) == [f"{YEAR}-{i:04d}" for i in range(1, 13)], f"gaps: {sorted(numbers)}"


def test_the_same_order_twice_gets_the_same_number():
    order = make_order()
    first = create_invoice(order)
    assert create_invoice(order) == first
    assert int(scalar(f"SELECT COUNT(*) FROM invoices WHERE order_id={order}")) == 1


def test_the_same_order_at_the_same_moment_still_gets_one_invoice():
    order = make_order()
    with ThreadPoolExecutor(max_workers=4) as pool:
        numbers = list(pool.map(lambda _: create_invoice(order), range(4)))
    assert len(set(numbers)) == 1
    assert int(scalar(f"SELECT COUNT(*) FROM invoices WHERE order_id={order}")) == 1


def test_invoice_total_and_order_status():
    order = make_order()
    number = create_invoice(order)
    assert scalar(f"SELECT total_cents FROM invoices WHERE invoice_number='{number}'") == "18029"
    assert scalar(f"SELECT status FROM orders WHERE id={order}") == "invoiced"


def test_unknown_order_is_an_error_and_the_counter_does_not_move():
    before = scalar(f"SELECT COALESCE(MAX(last_number), 0) FROM invoice_counters WHERE year={YEAR}")
    result = _run(["ddev", "mysql", "-N", "-B", "-e", f"CALL create_invoice(999999999, {YEAR})"])
    assert result.returncode != 0 and "Order not found" in result.stderr
    after = scalar(f"SELECT COALESCE(MAX(last_number), 0) FROM invoice_counters WHERE year={YEAR}")
    assert before == after