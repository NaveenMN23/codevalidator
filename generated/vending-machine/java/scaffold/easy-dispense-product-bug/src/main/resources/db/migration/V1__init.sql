CREATE TABLE product (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    price DOUBLE NOT NULL,
    quantity INT NOT NULL
);

INSERT INTO product (name, price, quantity) VALUES
('Soda', 1.50, 10),
('Chips', 1.00, 5),
('Candy', 0.75, 20),
('Juice', 2.00, 8);
