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

-- Gap-free invoice numbering: one counter row per year, increased inside a transaction:
--   START TRANSACTION;
--   INSERT INTO invoice_counters (year, last_number) VALUES (2026, 0) ON DUPLICATE KEY UPDATE year = year;
--   SELECT last_number FROM invoice_counters WHERE year = 2026 FOR UPDATE;
--   UPDATE invoice_counters SET last_number = last_number + 1 WHERE year = 2026;
--   ... insert the invoice with number CONCAT('2026-', LPAD(new_number, 4, '0')) ...
--   COMMIT;
-- Two people (or two workflows) can never get the same number, which is what went wrong in February.
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