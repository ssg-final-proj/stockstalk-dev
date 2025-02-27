import os
import sys
import logging
import threading
import json
import atexit
import time
import redis
import requests
import pytz
from redis.lock import Lock
from datetime import datetime
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from kafka import KafkaConsumer
from dotenv import load_dotenv
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Import configuration and database modules
from config import config, current_config, ENV
from .route import redis_client_user, redis_client_stock, portfolio, redis_client_lock, redis_client_profit
from db import db, init_app, Order, Stock, Portfolio

# Add project root directory to the path if needed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

redis_lock_timeout = 3

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask extensions
migrate = Migrate()
scheduler = BackgroundScheduler()

# Define KST timezone
KST = pytz.timezone('Asia/Seoul')

def create_app():
    app = Flask(__name__)
    env = os.getenv('FLASK_ENV', 'default')
    app.config.from_object(config[env])
    app.config['SQLALCHEMY_DATABASE_URI'] = config[env].SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['ENV'] = env

    CORS(app, resources={r"/*": {"origins": "*"}})

    init_app(app, current_config.PORTFOLIO_SCHEMA)
    migrate.init_app(app, db, include_schemas=True)

    app.register_blueprint(portfolio)

    @app.route('/')
    def index():
        return render_template('index.html')

    def check_pending_orders():
        with app.app_context():
            logger.info("Checking pending orders...")
            session = db.session()
            try:
                pending_orders = session.query(Order).filter_by(status='PENDING').all()
                for order in pending_orders:
                    stock = session.query(Stock).filter_by(stock_symbol=order.stock_symbol).first()
                    if not stock:
                        logger.warning(f"Stock not found for symbol: {order.stock_symbol}, skipping order {order.id}")
                        continue
                    current_price_data = redis_client_stock.get(f'stock_data:{stock.stock_symbol}')
                    if current_price_data:
                        try:
                            current_price = json.loads(current_price_data)['price']
                            if order.order_type.upper() == 'BUY' and order.target_price >= current_price:
                                logger.info(f"Reprocessing pending order {order.id}...")
                                handle_order_event({
                                    'kakao_id': order.kakao_id,
                                    'stock_symbol': stock.stock_symbol,
                                    'stock_name': stock.stock_name,
                                    'order_type': order.order_type,
                                    'quantity': order.quantity,
                                    'target_price': order.target_price
                                })
                        except (json.JSONDecodeError, TypeError, KeyError) as e:
                            logger.error(f"Error parsing or accessing stock data for symbol {stock.stock_symbol}: {e}", exc_info=True)
                    else:
                        logger.warning(f"Current price data not found in Redis for stock: {stock.stock_symbol}")
                session.commit()
            except Exception as e:
                session.rollback()
                logger.error(f"Error checking pending orders: {e}", exc_info=True)
            finally:
                session.close()

    def run_check_pending_orders():
        with app.app_context():
            check_pending_orders()

    scheduler.add_job(
        func=run_check_pending_orders,
        trigger=IntervalTrigger(seconds=60),
        id='check_pending_orders_job',
        name='Check pending orders every 60 seconds',
        replace_existing=True
    )

    def sync_profit_rates_to_db():
        with app.app_context():
            logger.info("Syncing profit rates to database...")
            session = db.session()
            try:
                profit_rate_keys = redis_client_profit.keys('profit_rate:*')
                for key in profit_rate_keys:
                    try:
                        parts = key.split(':')
                        if len(parts) != 3:
                            logger.warning(f"Invalid profit rate key format: {key}")
                            continue
                        _, kakao_id, stock_symbol = parts

                        profit_rate = redis_client_profit.get(key)
                        if profit_rate is None:
                            logger.warning(f"No profit rate found for key: {key}")
                            continue

                        profit_rate = float(profit_rate)

                        portfolio_entry = session.query(Portfolio).filter_by(
                            kakao_id=kakao_id, stock_symbol=stock_symbol).first()
                        if portfolio_entry:
                            portfolio_entry.profit_rate = profit_rate
                            logger.info(
                                f"Updated profit rate for kakao_id: {kakao_id}, stock_symbol: {stock_symbol} to {profit_rate}")
                        else:
                            logger.warning(
                                f"Portfolio entry not found for kakao_id: {kakao_id}, stock_symbol: {stock_symbol}")

                    except Exception as e:
                        logger.error(f"Error syncing profit rate for key {key}: {e}", exc_info=True)

                session.commit()
                logger.info("Profit rates synced to database successfully.")

            except Exception as e:
                session.rollback()
                logger.error(f"Error during profit rate synchronization: {e}", exc_info=True)
            finally:
                session.close()

    def run_sync_profit_rates_to_db():
        with app.app_context():
            sync_profit_rates_to_db()

    scheduler.add_job(
        func=run_sync_profit_rates_to_db,
        trigger=IntervalTrigger(seconds=300),
        id='sync_profit_rates_job',
        name='Sync profit rates from Redis to DB every 5 minutes',
        replace_existing=True
    )

    try:
        scheduler.start()
        logger.info("Scheduler started")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}", exc_info=True)

    logger.info("Starting Kafka consumer thread...")
    consumer_thread = threading.Thread(target=consume_order_events, args=(app,), daemon=True)
    consumer_thread.start()
    logger.info("Kafka consumer thread started")

    atexit.register(lambda: scheduler.shutdown(wait=False))

    return app

def consume_order_events(app):
    logger.info("Entering consume_order_events function")
    try:
        with app.app_context():
            consumer = KafkaConsumer(
                'orders_topic',
                bootstrap_servers=[os.getenv('KAFKA_BROKER_HOST', 'kafka:9092')],
                auto_offset_reset='earliest',
                enable_auto_commit=False,
                group_id='portfolio-service',
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )
            logger.info("Kafka consumer set up complete")
            logger.info("Starting to consume messages...")
            for message in consumer:
                logger.info(f"Received raw message from Kafka: {message}")
                try:
                    logger.info(f"Received message from Kafka: {message.value}")
                    handle_order_event(message.value)
                    logger.info("Kafka offset will be committed")
                    consumer.commit()
                    logger.info("Kafka offset committed")
                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Kafka Consumer error: {e}", exc_info=True)
        sys.exit(1)

# Define KST timezone
KST = pytz.timezone('Asia/Seoul')

def get_kst_now():
    utc_now = datetime.utcnow()
    kst_now = utc_now.replace(tzinfo=pytz.utc).astimezone(KST)
    return kst_now

def handle_order_event(event):
    logger.info(f"Handling order event: {event}")

    session = db.session()
    try:
        session.begin()

        stock_symbol = event['stock_symbol']
        stock_name = event['stock_name']

        stock = session.query(Stock).filter_by(stock_symbol=stock_symbol).first()
        if not stock:
            stock = Stock(stock_symbol=stock_symbol, stock_name=stock_name, market="DOMESTIC")
            session.add(stock)
            logger.info(f"New stock added: {stock.stock_name}")

        new_order = Order(
            kakao_id=event['kakao_id'],
            stock_symbol=stock_symbol,
            order_type=event['order_type'],
            target_price=event['target_price'],
            quantity=event['quantity'],
            status='PENDING',
            created_at=get_kst_now()  # Use KST
        )
        session.add(new_order)
        logger.info(f"New order recorded: Order ID {new_order.id}")

        process_order(event, session)

        session.commit()
        logger.info(f"Order event handled successfully. Order ID: {new_order.id}")

    except Exception as e:
        session.rollback()
        logger.error(f"Error handling order event: {e}", exc_info=True)
    finally:
        session.close()

def update_user_in_auth_service(kakao_id, seed_krw):
    update_url = "http://3.34.97.76:8001/auth/api/update_user"
    try:
        user_data_str = redis_client_user.get(f'session:{kakao_id}')
        if not user_data_str:
            raise ValueError(f"User data not found for kakao_id: {kakao_id}")

        user_data = json.loads(user_data_str)

        response = requests.post(update_url, json={
            "kakao_id": kakao_id,
            "seed_krw": seed_krw,
            "seed_usd": user_data['seed_usd']
        })

        if response.status_code != 200:
            logger.error(f"Auth service 업데이트 실패: {response.text}")
            raise Exception("Auth service update failed")

        logger.info("Auth service 업데이트 성공")
    except Exception as e:
        logger.error(f"Auth 서비스 업데이트 중 오류 발생: {str(e)}")
        raise

def process_buy_order(event, session, user_data, current_price, order, portfolio_entry):
    kakao_id = event['kakao_id']
    stock_symbol = event['stock_symbol']
    quantity = int(event['quantity'])
    total_cost = quantity * current_price

    user_seed_krw = float(user_data.get('seed_krw', 0))

    if user_seed_krw >= total_cost and order.target_price >= current_price:
        if not portfolio_entry:
            portfolio_entry = Portfolio(
                kakao_id=kakao_id,
                stock_symbol=stock_symbol,
                stock_amount=quantity,
                total_value=total_cost,
                initial_investment=total_cost,
                profit_rate=0.0
            )
            session.add(portfolio_entry)
        else:
            portfolio_entry.stock_amount += quantity
            portfolio_entry.total_value = current_price * portfolio_entry.stock_amount
            portfolio_entry.initial_investment += total_cost

        user_seed_krw -= total_cost
        user_data['seed_krw'] = user_seed_krw
        redis_client_user.set(f'session:{kakao_id}', json.dumps(user_data), ex=86400)

        order.status = 'COMPLETED'
        order.completed_at = get_kst_now()  # 한국 시간으로 설정
        logger.info(f"BUY order processed successfully for kakao_id: {kakao_id}, stock: {stock_symbol}")

        update_user_in_auth_service(kakao_id, user_seed_krw)

        if portfolio_entry.initial_investment > 0:
            profit_rate = ((current_price * portfolio_entry.stock_amount) - portfolio_entry.initial_investment) / portfolio_entry.initial_investment * 100
        else:
            profit_rate = 0
        redis_client_profit.set(f'profit_rate:{kakao_id}:{stock_symbol}', profit_rate)
        portfolio_entry.profit_rate = profit_rate  # DB에도 저장
    else:
        logger.info(f"BUY order conditions not met for kakao_id: {kakao_id}, stock: {stock_symbol}")

def process_sell_order(event, session, user_data, current_price, order, portfolio_entry):
    kakao_id = event['kakao_id']
    stock_symbol = event['stock_symbol']
    quantity = int(event['quantity'])
    total_sale = quantity * current_price

    user_seed_krw = float(user_data.get('seed_krw', 0))

    if portfolio_entry and portfolio_entry.stock_amount >= quantity and order.target_price <= current_price:
        portfolio_entry.stock_amount -= quantity
        portfolio_entry.total_value = current_price * portfolio_entry.stock_amount

        user_seed_krw += total_sale
        user_data['seed_krw'] = user_seed_krw
        redis_client_user.set(f'session:{kakao_id}', json.dumps(user_data), ex=86400)

        order.status = 'COMPLETED'
        order.completed_at = get_kst_now()  # 한국 시간으로 설정
        logger.info(f"SELL order processed successfully for kakao_id: {kakao_id}, stock: {stock_symbol}")

        update_user_in_auth_service(kakao_id, user_seed_krw)

        if portfolio_entry.initial_investment > 0:
            profit_rate = ((current_price * portfolio_entry.stock_amount) - portfolio_entry.initial_investment) / portfolio_entry.initial_investment * 100
        else:
            profit_rate = 0
        redis_client_profit.set(f'profit_rate:{kakao_id}:{stock_symbol}', profit_rate)
        portfolio_entry.profit_rate = profit_rate  # DB에도 저장
    else:
        logger.info(f"SELL order conditions not met for kakao_id: {kakao_id}, stock: {stock_symbol}")

def process_order(event, session):
    kakao_id = event['kakao_id']
    stock_symbol = event['stock_symbol']
    order_type = event['order_type']
    quantity = int(event['quantity'])
    target_price = float(event['target_price'])

    lock = Lock(redis_client_lock, f'user_lock:{kakao_id}', timeout=redis_lock_timeout)
    try:
        with lock:
            user_data_str = redis_client_user.get(f'session:{kakao_id}')
            if not user_data_str:
                raise ValueError(f"User data not found for kakao_id: {kakao_id}")

            user_data = json.loads(user_data_str)
            current_price_data_str = redis_client_stock.get(f'stock_data:{stock_symbol}')
            if not current_price_data_str:
                raise ValueError(f"Current stock price not found for symbol: {stock_symbol}")

            current_price_data = json.loads(current_price_data_str)
            current_price = float(current_price_data.get('price', 0))

            order = session.query(Order).filter_by(
                kakao_id=kakao_id,
                stock_symbol=stock_symbol,
                order_type=order_type,
                quantity=quantity,
                target_price=target_price,
                status='PENDING'
            ).first()

            if not order:
                logger.warning(f"No matching PENDING order found for processing: kakao_id={kakao_id}, stock_symbol={stock_symbol}")
                return

            portfolio_entry = session.query(Portfolio).filter_by(kakao_id=kakao_id, stock_symbol=stock_symbol).first()

            if order_type.upper() == 'BUY':
                process_buy_order(event, session, user_data, current_price, order, portfolio_entry)
            elif order_type.upper() == 'SELL':
                process_sell_order(event, session, user_data, current_price, order, portfolio_entry)

            logger.info("Order processing completed successfully.")

    except Exception as e:
        session.rollback()
        logger.error(f"Error processing order: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8003, debug=False)
