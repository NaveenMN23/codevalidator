CREATE TABLE products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255),
    price DOUBLE,
    quantity INT
);

CREATE TABLE cash (
    id INT AUTO_INCREMENT PRIMARY KEY,
    denomination DOUBLE,
    quantity INT
);

INSERT INTO products (name, price, quantity) VALUES
('Soda', 1.25, 10),
('Chips', 1.00, 15),
('Candy', 0.75, 20);

INSERT INTO cash (denomination, quantity) VALUES
(0.25, 50),
(0.50, 30),
(1.00, 20),
(5.00, 10);
