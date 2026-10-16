-- Independent demo database. No DROP, DELETE or changes to the student database.
-- Import once into a new database. A repeat import intentionally fails on existing tables.
CREATE DATABASE IF NOT EXISTS commerce_ai_demo CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE commerce_ai_demo;

CREATE TABLE customers (
    customer_id INT PRIMARY KEY,
    customer_name VARCHAR(50) NOT NULL COMMENT 'Synthetic display name, no real personal information',
    region VARCHAR(20) NOT NULL,
    city VARCHAR(30) NOT NULL,
    registered_at DATE NOT NULL,
    INDEX idx_customer_region (region)
) ENGINE=InnoDB;

CREATE TABLE products (
    product_id INT PRIMARY KEY,
    product_name VARCHAR(80) NOT NULL,
    category VARCHAR(30) NOT NULL,
    list_price DECIMAL(10,2) NOT NULL,
    cost_price DECIMAL(10,2) NOT NULL,
    INDEX idx_product_category (category),
    CHECK (list_price > 0 AND cost_price >= 0)
) ENGINE=InnoDB;

CREATE TABLE orders (
    order_id INT PRIMARY KEY,
    customer_id INT NOT NULL,
    ordered_at DATETIME NOT NULL,
    paid_at DATETIME NULL,
    status VARCHAR(20) NOT NULL COMMENT 'paid/completed/cancelled/refunded; refunded means fully refunded',
    channel VARCHAR(20) NOT NULL COMMENT 'app/web/mini_program',
    paid_amount DECIMAL(12,2) NOT NULL COMMENT 'Original payment; fully refunded orders retain original amount',
    refund_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
    CONSTRAINT fk_order_customer FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    CHECK (status IN ('paid', 'completed', 'cancelled', 'refunded')),
    CHECK (paid_amount >= 0 AND refund_amount >= 0 AND refund_amount <= paid_amount),
    INDEX idx_order_status_date (status, ordered_at),
    INDEX idx_order_customer_date (customer_id, ordered_at)
) ENGINE=InnoDB;

CREATE TABLE order_items (
    item_id INT PRIMARY KEY,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL COMMENT 'Historical price before discount',
    unit_cost DECIMAL(10,2) NOT NULL COMMENT 'Historical product cost estimate',
    line_paid_amount DECIMAL(12,2) NOT NULL COMMENT 'Allocated actual payment after discount; zero for cancelled orders',
    CONSTRAINT fk_item_order FOREIGN KEY (order_id) REFERENCES orders(order_id),
    CONSTRAINT fk_item_product FOREIGN KEY (product_id) REFERENCES products(product_id),
    UNIQUE KEY uk_order_product (order_id, product_id),
    INDEX idx_item_product_order (product_id, order_id),
    CHECK (quantity > 0 AND unit_price > 0 AND unit_cost >= 0 AND line_paid_amount >= 0)
) ENGINE=InnoDB;
