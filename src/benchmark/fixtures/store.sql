PRAGMA foreign_keys = ON;

BEGIN;

CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0)
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES users (id),
    delivery_address TEXT NOT NULL
);

CREATE TABLE order_items (
    order_id INTEGER NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products (id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0),
    PRIMARY KEY (order_id, product_id)
);

INSERT INTO users (id, name) VALUES
    (1, 'Klient A'),
    (2, 'Klient B');

INSERT INTO products (id, name, price_cents) VALUES
    (10, 'Klawiatura', 14999),
    (11, 'Mysz', 7999),
    (12, 'Kabel USB-C', 2999);

INSERT INTO orders (id, customer_id, delivery_address) VALUES
    (101, 1, 'Testowa 1'),
    (102, 2, 'Testowa 2');

INSERT INTO order_items (order_id, product_id, quantity, unit_price_cents) VALUES
    (101, 10, 1, 14999),
    (101, 12, 2, 2999),
    (102, 10, 1, 14999);

COMMIT;
