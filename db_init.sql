
CREATE TABLE payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nonce TEXT,
  customer_id TEXT,
  payment_method_token TEXT,
  transaction_id TEXT,
  subscription_id TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
