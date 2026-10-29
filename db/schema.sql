-- LoopCasts database schema (replaces orders 2026.xlsx and the invoice register).
-- Load with:  ddev mysql < db/schema.sql
-- Amounts are stored in cents (integers) so there are no rounding surprises.

-- Simulated payment provider. Shaped like Mollie's payment object on purpose
-- (id, status, amount, metadata, webhook URL), so the real provider can replace it later.
CREATE TABLE IF NOT EXISTS payments (
  id            VARCHAR(40)  NOT NULL PRIMARY KEY,            -- like tr_test_ab12cd34
  status        ENUM('open','paid','failed','canceled','expired') NOT NULL DEFAULT 'open',
  amount_cents  INT UNSIGNED NOT NULL,
  currency      CHAR(3)      NOT NULL DEFAULT 'EUR',
  description   VARCHAR(200) NOT NULL,
  metadata      TEXT         NOT NULL,                        -- JSON with the order form details
  webhook_url   VARCHAR(300) NOT NULL,
  redirect_url  VARCHAR(300) NOT NULL,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  paid_at       DATETIME     NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- The order, written by n8n once a payment is confirmed as paid.
-- UNIQUE(payment_id): the same payment can never create two orders.
CREATE TABLE IF NOT EXISTS orders (
  id               INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  payment_id       VARCHAR(40)  NOT NULL,
  plan             ENUM('monthly','yearly','team','single') NOT NULL,
  course           VARCHAR(100) NULL,                          -- only for single courses
  name             VARCHAR(120) NOT NULL,
  email            VARCHAR(190) NOT NULL,
  company          VARCHAR(160) NULL,
  vat_number       VARCHAR(20)  NULL,
  country          CHAR(2)      NOT NULL,
  amount_excl_cents INT UNSIGNED NOT NULL,
  vat_cents        INT UNSIGNED NOT NULL DEFAULT 0,
  vat_rule         ENUM('belgian_21','reverse_charge') NOT NULL,
  status           ENUM('paid','invoiced','account_pending','account_created','failed') NOT NULL DEFAULT 'paid',
  created_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_orders_payment (payment_id),
  KEY idx_orders_status (status),
  KEY idx_orders_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Gap-free invoice numbering. The number is handed out by the procedure create_invoice() below, inside one
-- transaction, so two people (or two workflows) can never get the same number, which is what went wrong in February.
CREATE TABLE IF NOT EXISTS invoice_counters (
  year         SMALLINT UNSIGNED NOT NULL PRIMARY KEY,
  last_number  INT UNSIGNED NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS invoices (
  invoice_number VARCHAR(12) NOT NULL PRIMARY KEY,             -- 2026-0001
  order_id       INT UNSIGNED NOT NULL,
  issued_on      DATE         NOT NULL,
  total_cents    INT UNSIGNED NOT NULL,
  created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_invoices_order (order_id),
  CONSTRAINT fk_invoices_order FOREIGN KEY (order_id) REFERENCES orders (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- create_invoice(order_id, year): gives an order its invoice number, exactly once.
--  * locks the order row first, so two runs for the same order take turns (the second one just gets the same number back)
--  * locks the counter row of that year, so two different orders take turns (numbers are unique and have no gaps)
--  * if anything fails, everything is rolled back and the counter does not move
-- Returns one row: invoice_number. Reload this file at any time, CREATE OR REPLACE updates it.
DELIMITER //
CREATE OR REPLACE PROCEDURE create_invoice(IN p_order_id INT UNSIGNED, IN p_year SMALLINT UNSIGNED)
BEGIN
  DECLARE v_total  INT UNSIGNED DEFAULT NULL;
  DECLARE v_number VARCHAR(12)  DEFAULT NULL;
  DECLARE v_next   INT UNSIGNED;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  START TRANSACTION;

  SELECT amount_excl_cents + vat_cents INTO v_total FROM orders WHERE id = p_order_id FOR UPDATE;
  IF v_total IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Order not found';
  END IF;

  SET v_number = (SELECT invoice_number FROM invoices WHERE order_id = p_order_id);
  IF v_number IS NULL THEN
    INSERT INTO invoice_counters (year, last_number) VALUES (p_year, 0) ON DUPLICATE KEY UPDATE year = year;
    SELECT last_number + 1 INTO v_next FROM invoice_counters WHERE year = p_year FOR UPDATE;
    UPDATE invoice_counters SET last_number = v_next WHERE year = p_year;
    SET v_number = CONCAT(p_year, '-', LPAD(v_next, 4, '0'));
    INSERT INTO invoices (invoice_number, order_id, issued_on, total_cents)
      VALUES (v_number, p_order_id, CURDATE(), v_total);
    UPDATE orders SET status = 'invoiced' WHERE id = p_order_id AND status = 'paid';
  END IF;

  COMMIT;
  SELECT v_number AS invoice_number;
END//
DELIMITER ;