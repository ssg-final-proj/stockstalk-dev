import pymysql
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, text, ForeignKey
from config import current_config, ENV
import os

pymysql.install_as_MySQLdb()

db = SQLAlchemy()

def get_stock_by_symbol(stock_symbol):
    return Stock.query.filter_by(stock_symbol=stock_symbol).first()

def init_app(app, schema_name):
    db_uri = current_config.SQLALCHEMY_DATABASE_URI
    
    try:
        engine = create_engine(f"{db_uri}/{schema_name}", echo=True, pool_pre_ping=True, pool_recycle=3600)
        with engine.connect() as connection:
            connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS `{schema_name}`"))

        app.config['SQLALCHEMY_DATABASE_URI'] = f"{db_uri}/{schema_name}"
        
    except Exception as e:
        print(f"Error initializing the database: {e}")

class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = {"schema": current_config.AUTH_SCHEMA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    kakao_id = db.Column(db.String(20), unique=True, nullable=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=True, unique=True)
    seed_krw = db.Column(db.Float, default=0.0)
    seed_usd = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=db.func.now())
    last_login = db.Column(db.DateTime)
    last_seed_update = db.Column(db.DateTime, default=None)

class Stock(db.Model):
    __tablename__ = 'stocks'
    __table_args__ = {"schema": current_config.PORTFOLIO_SCHEMA}  # stock 테이블을 portfolio 스키마로 이동

    id = db.Column(db.Integer, primary_key=True)
    stock_symbol = db.Column(db.String(50), nullable=False, unique=True)
    stock_name = db.Column(db.String(255), nullable=False)
    market = db.Column(db.Enum('DOMESTIC', 'INTERNATIONAL', name='market_enum'), nullable=False)

class Portfolio(db.Model):
    __tablename__ = 'portfolios'
    __table_args__ = {"schema": current_config.PORTFOLIO_SCHEMA}

    id = db.Column(db.Integer, primary_key=True)
    kakao_id = db.Column(db.String(20), nullable=False)
    stock_symbol = db.Column(db.String(50), db.ForeignKey(f"{current_config.PORTFOLIO_SCHEMA}.stocks.stock_symbol", ondelete="CASCADE"), nullable=False)
    stock_amount = db.Column(db.Float, default=0.0)
    total_value = db.Column(db.Float, default=0.0)
    initial_investment = db.Column(db.Float, default=0.0)
    p_rank = db.Column(db.Integer, nullable=True)
    profit_rate = db.Column(db.Float, default=0.0)  # 수익률 컬럼 추가

    # 복합 인덱스 추가
    __table_args__ = (
        db.Index('idx_kakao_id_stock_symbol', 'kakao_id', 'stock_symbol'),
        {"schema": current_config.PORTFOLIO_SCHEMA}
    )

class Order(db.Model):
    __tablename__ = 'orders'
    __table_args__ = {"schema": current_config.PORTFOLIO_SCHEMA}

    id = db.Column(db.Integer, primary_key=True)
    kakao_id = db.Column(db.String(20), nullable=False)
    stock_symbol = db.Column(db.String(50), db.ForeignKey(f"{current_config.PORTFOLIO_SCHEMA}.stocks.stock_symbol", ondelete="CASCADE"), nullable=False)
    order_type = db.Column(db.Enum('BUY', 'SELL', name='order_type_enum'), nullable=False)
    target_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.Enum('PENDING', 'COMPLETED', name='order_status_enum'), default='PENDING')
    created_at = db.Column(db.DateTime, default=db.func.now())
    completed_at = db.Column(db.DateTime, nullable=True)

class Exchange(db.Model):
    __tablename__ = 'exchanges'
    __table_args__ = {"schema": current_config.EXCHANGE_SCHEMA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    kakao_id = db.Column(db.String(20), nullable=False)
    from_currency = db.Column(db.String(10), nullable=False)
    to_currency = db.Column(db.String(10), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    exchange_rate = db.Column(db.Float, nullable=False)
    total_value = db.Column(db.Float, nullable=False)
    exchange_date = db.Column(db.DateTime, default=db.func.now())
