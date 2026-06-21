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
    status TEXT,
    FOREIGN KEY (product_id) REFERENCES products(id)
  );

  INSERT INTO products (name, price, quantity) VALUES
    ('Soda', 150, 10),
    ('Chips', 100, 5),
    ('Candy', 50, 20);
`);

export default db;
