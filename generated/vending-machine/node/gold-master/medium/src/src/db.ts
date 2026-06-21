import Database from 'better-sqlite3';

const db = new Database(':memory:');

db.exec(`
  CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT,
    price INTEGER,
    quantity INTEGER
  );
  CREATE TABLE transactions (
    id INTEGER PRIMARY KEY,
    product_id INTEGER,
    amount_paid INTEGER,
    change_given INTEGER,
    status TEXT
  );
  CREATE TABLE coins (
    denomination INTEGER PRIMARY KEY,
    quantity INTEGER
  );
`);

db.exec(`
  INSERT INTO products (name, price, quantity) VALUES
  ('Soda', 150, 10),
  ('Chips', 100, 5),
  ('Candy', 50, 20);

  INSERT INTO coins (denomination, quantity) VALUES
  (100, 10),
  (50, 10),
  (25, 10),
  (10, 10),
  (5, 10),
  (1, 10);
`);

export default db;