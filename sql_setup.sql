-- Secure Multi-User Mobile Payment Simulation System Using Python and MySQL
-- Class 12 Computer Science Project SQL Setup

CREATE DATABASE IF NOT EXISTS mobile_payment_system;
USE mobile_payment_system;

CREATE TABLE IF NOT EXISTS users (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(64) NOT NULL,
    wallet_uid VARCHAR(50) NOT NULL UNIQUE,
    bank_uid VARCHAR(50) NOT NULL UNIQUE,
    balance FLOAT DEFAULT 0 CHECK (balance >= 0)
);

CREATE TABLE IF NOT EXISTS transactions (
    txn_id VARCHAR(50) PRIMARY KEY,
    sender_uid VARCHAR(50) NOT NULL,
    receiver_uid VARCHAR(50) NOT NULL,
    amount FLOAT NOT NULL CHECK (amount > 0),
    txn_type VARCHAR(50) NOT NULL,
    date_time DATETIME NOT NULL,
    status VARCHAR(50) NOT NULL,
    CONSTRAINT fk_sender_wallet FOREIGN KEY (sender_uid) REFERENCES users(wallet_uid),
    CONSTRAINT fk_receiver_wallet FOREIGN KEY (receiver_uid) REFERENCES users(wallet_uid)
);
