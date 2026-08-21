-- Safe Text-to-SQL sample database for PostgreSQL.
-- Run this inside an empty database named text2sql_demo.

BEGIN;

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    customer_name VARCHAR(255) NOT NULL,
    country VARCHAR(100) NOT NULL,
    segment VARCHAR(100) NOT NULL,
    created_at DATE NOT NULL
);

CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0)
);

CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date DATE NOT NULL,
    status VARCHAR(30) NOT NULL CHECK (status IN ('paid', 'pending', 'refunded')),
    total_amount NUMERIC(10, 2) NOT NULL CHECK (total_amount >= 0),
    discount_amount NUMERIC(10, 2) NOT NULL CHECK (discount_amount >= 0),
    net_amount NUMERIC(10, 2) NOT NULL CHECK (net_amount >= 0)
);

CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(order_id),
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    line_total NUMERIC(10, 2) NOT NULL CHECK (line_total >= 0)
);

CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_order_date ON orders(order_date);
CREATE INDEX idx_order_items_order_id ON order_items(order_id);

INSERT INTO customers (customer_id, customer_name, country, segment, created_at) VALUES
    (1, 'Aster Labs', 'India', 'Enterprise', '2024-01-15'),
    (2, 'Northwind Stores', 'United States', 'Mid-market', '2024-02-02'),
    (3, 'Cedar & Co', 'United Kingdom', 'SMB', '2024-02-28'),
    (4, 'Mosaic Health', 'India', 'Enterprise', '2024-03-10'),
    (5, 'Orbit Supply', 'Australia', 'Mid-market', '2024-03-19');

INSERT INTO products (product_id, product_name, category, unit_price) VALUES
    (1, 'Analytics Pro', 'Software', 1200.00),
    (2, 'Data Connector', 'Software', 650.00),
    (3, 'Implementation', 'Services', 2500.00),
    (4, 'Priority Support', 'Services', 800.00);

INSERT INTO orders (order_id, customer_id, order_date, status, total_amount, discount_amount, net_amount) VALUES
    (1001, 1, '2024-04-03', 'paid', 3700.00, 200.00, 3500.00),
    (1002, 2, '2024-04-18', 'paid', 1850.00, 0.00, 1850.00),
    (1003, 1, '2024-05-05', 'paid', 1200.00, 0.00, 1200.00),
    (1004, 3, '2024-05-21', 'refunded', 2500.00, 250.00, 2250.00),
    (1005, 4, '2024-06-02', 'paid', 3300.00, 300.00, 3000.00),
    (1006, 5, '2024-06-11', 'pending', 650.00, 0.00, 650.00),
    (1007, 2, '2024-06-28', 'paid', 2000.00, 0.00, 2000.00);

INSERT INTO order_items (order_item_id, order_id, product_id, quantity, line_total) VALUES
    (1, 1001, 1, 1, 1200.00), (2, 1001, 3, 1, 2500.00),
    (3, 1002, 1, 1, 1200.00), (4, 1002, 2, 1, 650.00),
    (5, 1003, 1, 1, 1200.00), (6, 1004, 3, 1, 2500.00),
    (7, 1005, 3, 1, 2500.00), (8, 1005, 4, 1, 800.00),
    (9, 1006, 2, 1, 650.00), (10, 1007, 1, 1, 1200.00),
    (11, 1007, 4, 1, 800.00);

COMMIT;
