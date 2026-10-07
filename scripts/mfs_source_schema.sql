CREATE TABLE customers (
  customer_id varchar(64) PRIMARY KEY,
  display_name varchar(255),
  phone varchar(32),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE wallets (
  wallet_id varchar(64) PRIMARY KEY,
  customer_id varchar(64) NOT NULL REFERENCES customers(customer_id),
  status varchar(20) NOT NULL DEFAULT 'ACTIVE'
);
CREATE TABLE transactions (
  transaction_id varchar(64) PRIMARY KEY,
  wallet_id varchar(64) NOT NULL REFERENCES wallets(wallet_id),
  amount numeric(18,2) NOT NULL,
  currency char(3) NOT NULL DEFAULT 'BDT',
  status varchar(20) NOT NULL,
  occurred_at timestamptz NOT NULL
);
CREATE INDEX transactions_occurred_at_idx ON transactions(occurred_at);
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mfs_reader;
