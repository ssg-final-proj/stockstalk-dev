import pymysql
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, text, ForeignKey, Integer, Float, String, DateTime, Enum
from sqlalchemy.sql import func
from config import current_config

pymysql.install_as_MySQLdb()

db = SQLAlchemy()

def init_app(app, schema_name):
    db_uri = current_config.SQLALCHEMY_DATABASE_URI
    
    try:
        engine = create_engine(db_uri, echo=True, pool_pre_ping=True, pool_recycle=3600)
        with engine.connect() as connection:
            connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS `{schema_name}`"))

    except Exception as e:
        print(f"Error initializing the database: {e}")

class User(db.Model):
    __tablename__ = 'users'
    __bind_key__ = 'auth'
    __table_args__ = {"schema": current_config.AUTH_SCHEMA}

    id = db.Column(Integer, primary_key=True, autoincrement=True)
    kakao_id = db.Column(String(20), unique=True, nullable=True)
    username = db.Column(String(80), nullable=False, unique=True)
    email = db.Column(String(150), nullable=True, unique=True)
    email_verified = db.Column(db.Boolean, default=False)  # ✅ 이메일 검증 필드 추가
    seed_krw = db.Column(Float, default=0.0)
    seed_usd = db.Column(Float, default=0.0)
    created_at = db.Column(DateTime, default=func.now())
    last_login = db.Column(DateTime)
    last_seed_update = db.Column(DateTime)

class Stock(db.Model):
    __tablename__ = 'stocks'
    __bind_key__ = 'portfolio'
    __table_args__ = {"schema": current_config.PORTFOLIO_SCHEMA}

    id = db.Column(Integer, primary_key=True)
    stock_symbol = db.Column(String(50), nullable=False, unique=True)
    stock_name = db.Column(String(255), nullable=False)
    market = db.Column(Enum('DOMESTIC', 'INTERNATIONAL', name='market_enum'), nullable=False)

class Portfolio(db.Model):
    __tablename__ = 'portfolios'
    __bind_key__ = 'portfolio'
    __table_args__ = {"schema": current_config.PORTFOLIO_SCHEMA}

    id = db.Column(Integer, primary_key=True)
    kakao_id = db.Column(String(20), nullable=False)
    stock_symbol = db.Column(String(50), ForeignKey(f"{current_config.PORTFOLIO_SCHEMA}.stocks.stock_symbol", ondelete="CASCADE"), nullable=False)
    stock_amount = db.Column(Float, default=0.0)
    total_value = db.Column(Float, default=0.0)
    initial_investment = db.Column(Float, default=0.0)
    p_rank = db.Column(Integer, nullable=True)
    profit_rate = db.Column(Float, default=0.0)

    __table_args__ = (
        db.Index('idx_kakao_id_stock_symbol', 'kakao_id', 'stock_symbol'),
        {"schema": current_config.PORTFOLIO_SCHEMA}
    )

class Order(db.Model):
    __tablename__ = 'orders'
    __bind_key__ = 'portfolio'
    __table_args__ = {"schema": current_config.PORTFOLIO_SCHEMA}

    id = db.Column(Integer, primary_key=True)
    kakao_id = db.Column(String(20), nullable=False)
    stock_symbol = db.Column(String(50), ForeignKey(f"{current_config.PORTFOLIO_SCHEMA}.stocks.stock_symbol", ondelete="CASCADE"), nullable=False)
    order_type = db.Column(Enum('BUY', 'SELL', name='order_type_enum'), nullable=False)
    target_price = db.Column(Float, nullable=False)
    quantity = db.Column(Integer, nullable=False)
    status = db.Column(Enum('PENDING', 'COMPLETED', name='order_status_enum'), default='PENDING')
    created_at = db.Column(DateTime, default=func.now())
    completed_at = db.Column(DateTime, nullable=True)

class Exchange(db.Model):
    __tablename__ = 'exchanges'
    __bind_key__ = 'exchange'
    __table_args__ = {"schema": current_config.EXCHANGE_SCHEMA}

    id = db.Column(Integer, primary_key=True, autoincrement=True)
    kakao_id = db.Column(String(20), nullable=False)
    from_currency = db.Column(String(10), nullable=False)
    to_currency = db.Column(String(10), nullable=False)
    amount = db.Column(Float, nullable=False)
    exchange_rate = db.Column(Float, nullable=False)
    total_value = db.Column(Float, nullable=False)
    exchange_date = db.Column(DateTime, default=func.now())

# ✅ portfolio_ranking 모델 추가 (DENSE_RANK 순위 적용)
class PortfolioRanking(db.Model):
    __tablename__ = 'portfolio_ranking'
    __bind_key__ = 'portfolio'
    __table_args__ = {"schema": current_config.PORTFOLIO_SCHEMA}

    id = db.Column(Integer, primary_key=True, autoincrement=True)
    kakao_id = db.Column(String(20), unique=True, nullable=False)
    profit_rate_total = db.Column(Float, default=0.0)
    p_rank = db.Column(Integer, nullable=True)