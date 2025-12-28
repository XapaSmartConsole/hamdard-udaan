-- ==============================
-- DATABASE
-- ==============================
DROP DATABASE IF EXISTS rspl_demo;

CREATE DATABASE IF NOT EXISTS rspl_demo;
USE rspl_demo;

-- ==============================
-- USERS
-- ==============================
CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  full_name VARCHAR(100) NOT NULL,
  phone VARCHAR(15) UNIQUE NOT NULL,
  otp VARCHAR(6),
  otp_verified BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==============================
-- KYC (DOCUMENT BASED)
-- ==============================
CREATE TABLE IF NOT EXISTS kyc (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT UNIQUE NOT NULL,
  document_type VARCHAR(20),
  document_number VARCHAR(30),
  status VARCHAR(20) DEFAULT 'PENDING',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ==============================
-- BANK DETAILS
-- ==============================
CREATE TABLE IF NOT EXISTS bank_details (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT UNIQUE NOT NULL,
  account_holder_name VARCHAR(100) NOT NULL,
  bank_name VARCHAR(50) NOT NULL,
  account_number VARCHAR(20) NOT NULL,
  ifsc VARCHAR(15) NOT NULL,
  cheque_image VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ==============================
-- WALLET (🔥 FIXED STRUCTURE)
-- ==============================
CREATE TABLE IF NOT EXISTS wallet (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT UNIQUE NOT NULL,
  available_points INT DEFAULT 0,
  redeemed_points INT DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
ALTER TABLE wallet DROP COLUMN amount;
DESCRIBE wallet;
-- Rename columns to match backend model
ALTER TABLE wallet 
CHANGE available_points points INT DEFAULT 6000;

ALTER TABLE wallet 
CHANGE redeemed_points redeemed INT DEFAULT 0;

select * from users;
ALTER TABLE users ADD COLUMN email VARCHAR(100);
ALTER TABLE users ADD COLUMN profile_picture TEXT;
ALTER TABLE users ADD COLUMN region VARCHAR(50);
ALTER TABLE users ADD COLUMN state VARCHAR(50);
ALTER TABLE users ADD COLUMN city VARCHAR(50);

-- Drop and recreate table
DROP TABLE IF EXISTS kyc;

CREATE TABLE kyc (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    document_type VARCHAR(50) NOT NULL,
    document_number VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'COMPLETED',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_document (user_id, document_type),
    INDEX idx_user_kyc (user_id)
);

-- Create orders table
-- Drop existing tables (if you don't have important data)
-- Drop old tables
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;

-- Create new orders table
CREATE TABLE orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    order_id VARCHAR(50) UNIQUE NOT NULL,
    total_points INT NOT NULL,
    delivery_address TEXT,
    mobile VARCHAR(20),
    status VARCHAR(50) DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_orders (user_id),
    INDEX idx_order_id (order_id)
);

-- Create new order_items table
CREATE TABLE order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id VARCHAR(50) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    product_image TEXT,
    points INT NOT NULL,
    quantity INT DEFAULT 1,
    category VARCHAR(100),
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    INDEX idx_order_items (order_id)
);
select * FROM users;

ALTER TABLE bank_details MODIFY COLUMN cheque_image LONGTEXT;
ALTER TABLE users ADD COLUMN address TEXT;
ALTER TABLE users ADD COLUMN pincode VARCHAR(10);
ALTER TABLE orders ADD COLUMN transaction_type VARCHAR(20) DEFAULT 'PRODUCT';

-- Update existing orders to be PRODUCT type
UPDATE orders SET transaction_type = 'PRODUCT' WHERE transaction_type IS NULL;
ALTER TABLE users ADD COLUMN member_type VARCHAR(50);
ALTER TABLE users ADD COLUMN slab VARCHAR(50);
ALTER TABLE users ADD COLUMN distributor_name VARCHAR(100);
ALTER TABLE users ADD COLUMN target INTEGER;
ALTER TABLE users MODIFY COLUMN profile_picture LONGTEXT;
USE rspl_demo;

-- Add ham_code column
ALTER TABLE users ADD COLUMN ham_code VARCHAR(20) UNIQUE;

-- Generate HAM codes for existing users
SET @counter = 0;
UPDATE users 
SET ham_code = CONCAT('HAM', LPAD(@counter := @counter + 1, 6, '0'))
WHERE ham_code IS NULL
ORDER BY id;
ALTER TABLE users ADD COLUMN be_name VARCHAR(100) AFTER ham_code;

ALTER TABLE bank_details ADD COLUMN is_validated BOOLEAN DEFAULT FALSE AFTER cheque_image;
ALTER TABLE bank_details ADD COLUMN validation_status VARCHAR(20) DEFAULT 'PENDING';



CREATE TABLE IF NOT EXISTS transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    transaction_type VARCHAR(50) NOT NULL,
    points INT NOT NULL,
    amount INT NULL,
    description TEXT NULL,
    status VARCHAR(20) DEFAULT 'COMPLETED',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
ALTER TABLE users ADD COLUMN outlet_name VARCHAR(100) AFTER be_name;