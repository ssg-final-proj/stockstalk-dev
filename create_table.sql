-- 스키마 생성
CREATE SCHEMA IF NOT EXISTS auth_db;
CREATE SCHEMA IF NOT EXISTS portfolio_db;
CREATE SCHEMA IF NOT EXISTS exchange_db;

-- auth_db.users 테이블 생성 (✅ email_verified 필드 추가됨)
CREATE TABLE IF NOT EXISTS auth_db.users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    kakao_id VARCHAR(20) UNIQUE,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(150) UNIQUE,
    email_verified BOOLEAN DEFAULT FALSE, -- ✅ 이메일 검증 여부 필드 추가
    seed_krw FLOAT DEFAULT 0.0,
    seed_usd FLOAT DEFAULT 0.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME,
    last_seed_update DATETIME
);

-- portfolio_db.stocks 테이블 생성
CREATE TABLE IF NOT EXISTS portfolio_db.stocks (
    id INT PRIMARY KEY AUTO_INCREMENT,
    stock_symbol VARCHAR(50) NOT NULL UNIQUE,
    stock_name VARCHAR(255) NOT NULL,
    market ENUM('DOMESTIC', 'INTERNATIONAL') NOT NULL
);

-- portfolio_db.portfolios 테이블 생성
CREATE TABLE IF NOT EXISTS portfolio_db.portfolios (
    id INT PRIMARY KEY AUTO_INCREMENT,
    kakao_id VARCHAR(20) NOT NULL,
    stock_symbol VARCHAR(50) NOT NULL,
    stock_amount FLOAT DEFAULT 0.0,
    total_value FLOAT DEFAULT 0.0,
    initial_investment FLOAT DEFAULT 0.0,
    p_rank INT,
    profit_rate FLOAT DEFAULT 0.0,
    INDEX idx_kakao_id_stock_symbol (kakao_id, stock_symbol)
);

-- portfolio_db.orders 테이블 생성
CREATE TABLE IF NOT EXISTS portfolio_db.orders (
    id INT PRIMARY KEY AUTO_INCREMENT,
    kakao_id VARCHAR(20) NOT NULL,
    stock_symbol VARCHAR(50) NOT NULL,
    order_type ENUM('BUY', 'SELL') NOT NULL,
    target_price FLOAT NOT NULL,
    quantity INT NOT NULL,
    status ENUM('PENDING', 'COMPLETED') DEFAULT 'PENDING',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    INDEX idx_stock_symbol (stock_symbol)
);

-- ✅ portfolio_db.portfolio_ranking 테이블 생성 (순위 저장용)
CREATE TABLE IF NOT EXISTS portfolio_db.portfolio_ranking (
    id INT PRIMARY KEY AUTO_INCREMENT,
    kakao_id VARCHAR(20) NOT NULL UNIQUE,
    profit_rate_total FLOAT DEFAULT 0.0,
    p_rank INT
);

-- exchange_db.exchanges 테이블 생성
CREATE TABLE IF NOT EXISTS exchange_db.exchanges (
    id INT PRIMARY KEY AUTO_INCREMENT,
    kakao_id VARCHAR(20) NOT NULL,
    from_currency VARCHAR(10) NOT NULL,
    to_currency VARCHAR(10) NOT NULL,
    amount FLOAT NOT NULL,
    exchange_rate FLOAT NOT NULL,
    total_value FLOAT NOT NULL,
    exchange_date DATETIME DEFAULT CURRENT_TIMESTAMP
);