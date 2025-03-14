import os
import sys
import asyncio
import logging
from datetime import datetime
from flask_migrate import Migrate
from kafka import KafkaProducer
import redis
import threading
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from functools import wraps
import requests
import json
from config import current_config, ENV
import logging
from flask_socketio import SocketIO, emit  # Import SocketIO and emit
logger = logging.getLogger(__name__)

# 환경 변수 로드
load_dotenv()

# 시스템 경로 조정
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.join(os.path.abspath(os.path.dirname(__file__)), '../..'))

# 라우트 및 설정 가져오기
from route import *
from config import config

# Kafka Producer 설정
producer = KafkaProducer(
    bootstrap_servers=os.getenv('KAFKA_BROKER_HOST', 'kafka:9092'),
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# 로깅 설정
logging.basicConfig(level=logging.INFO)

CACHE_DURATION = 60

def sync(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

class BackgroundTasks:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BackgroundTasks, cls).__new__(cls)
            cls._instance.background_loop = None
            cls._instance.update_task = None
            cls._instance.is_running = False
            cls._instance._stop_event = threading.Event()
            cls._instance.background_thread = None
        return cls._instance

    async def run_tasks(self, redis_client_stock, fetch_all_stock_data, cache_duration):
        await preload_stock_data(redis_client_stock, fetch_all_stock_data, cache_duration)
        while not self._stop_event.is_set():
            try:
                logging.info("Fetching updated stock data...")
                stock_data_list = await fetch_all_stock_data(redis_client_stock)
                if stock_data_list:
                    logging.info("Updating Redis with new stock data")
                    redis_client_stock.setex('realtime_stock_data', cache_duration, json.dumps(stock_data_list))
                    logging.info("Redis update successful")
                else:
                    logging.error("Stock data update failed: empty list")
            except Exception as e:
                logging.error(f"Stock data update error: {e}")
            await asyncio.sleep(10)
        logging.info("Background task loop ended")

    def start(self, redis_client_stock, fetch_all_stock_data, cache_duration):
        if self.is_running:
            logging.info("Background tasks are already running.")
            return

        def run_async_loop(loop):
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    self.run_tasks(redis_client_stock, fetch_all_stock_data, cache_duration)
                )
            except Exception as e:
                logging.error(f"Background task error: {e}")
            finally:
                if not self._stop_event.is_set():  # 중단되지 않았다면 재시작
                    logging.info("Restarting background tasks due to unexpected termination")
                    self.start(redis_client_stock, fetch_all_stock_data, cache_duration)

        self._stop_event.clear()
        self.background_loop = asyncio.new_event_loop()
        self.background_thread = threading.Thread(
            target=run_async_loop,
            args=(self.background_loop,),
            daemon=True
        )
        self.background_thread.start()
        self.is_running = True
        logging.info("Background tasks started successfully")

    def stop(self):
        if not self.is_running:
            return
            
        logging.info("Stopping background tasks...")
        self._stop_event.set()
        if self.background_thread:
            self.background_thread.join(timeout=5)
        self.is_running = False
        logging.info("Background tasks stopped successfully")

redis_client_stock = None
redis_client_user = None

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'secret!')
    CORS(app, resources={r"/*": {"origins": current_config.BASE_URL}}, supports_credentials=True)
    app.logger.setLevel(logging.INFO)

    # Background tasks 관리자 초기화
    background_tasks = BackgroundTasks()

    env = os.getenv('FLASK_ENV', 'development')
    app.config.from_object(config[env])

    # Redis 클라이언트 초기화
    global redis_client_stock, redis_client_user
    try:
        redis_client_stock = redis.StrictRedis(
            host=app.config['REDIS_HOST'],
            port=app.config['REDIS_PORT'],
            db=0,  # Stock data db
            decode_responses=True
        )
        redis_client_user = redis.StrictRedis(
            host=app.config['REDIS_HOST'],
            port=app.config['REDIS_PORT'],
            db=1,  # User data db
            decode_responses=True
        )
        logger.info("Redis clients initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Redis clients: {e}", exc_info=True)
        sys.exit(1)
        
    app.config['REDIS_CLIENT_STOCK'] = redis_client_stock
    app.config['REDIS_CLIENT_USER'] = redis_client_user
    app.config['CACHE_DURATION'] = CACHE_DURATION

    # SocketIO 초기화 (전역으로 이동)
    global socketio
    socketio = SocketIO(app, cors_allowed_origins="*")

    # SocketIO 이벤트 핸들러
    @socketio.on('connect', namespace='/stock')
    def connect_handler():
        print('Client connected')
    
    with app.app_context():
        # 앱 시작 시 백그라운드 태스크 시작
        background_tasks.start(redis_client_stock, fetch_all_stock_data, app.config['CACHE_DURATION'])

    @app.route('/')
    def home():
        kakao_id = request.cookies.get('kakao_id')
        app.logger.info(f"✅ 쿠키에서 kakao_id 확인: {kakao_id}")

        user_data = None
        if kakao_id:
            try:
                user_data = redis_client_user.get(f'session:{kakao_id}')
                app.logger.info(f"✅ Redis에서 가져온 사용자 데이터: {user_data}")
            except Exception as e:
                app.logger.error(f"Redis에서 사용자 데이터를 가져오는 중 오류 발생: {e}")

        if user_data:
            user_data = json.loads(user_data)

        return render_template('stock_kr.html', user_data=user_data, config=current_config)  # ✅ config 전달
    
    @app.route('/login')
    def login():
        return redirect(f'{current_config.AUTH_SERVICE_URL}')

    @app.route('/api/realtime-stock-data', methods=['GET'])
    @sync
    async def realtime_stock_data():
        force_update = request.args.get('force_update', 'false').lower() == 'true'

        try:
            if not force_update:
                cached_data = redis_client_stock.get('realtime_stock_data')
                if cached_data:
                    logging.info("Serving data from Redis cache")
                    return jsonify(json.loads(cached_data))

            logging.info("Fetching realtime stock data from API")
            stock_data_list = await fetch_all_stock_data(redis_client_stock)
            redis_client_stock.setex('realtime_stock_data', CACHE_DURATION, json.dumps(stock_data_list))

            return jsonify(stock_data_list)
        except Exception as e:
            app.logger.error(f"Error fetching realtime stock data: {e}", exc_info=True)
            return jsonify({"error": "Failed to fetch realtime stock data"}), 500

    @app.route('/api/stock-full-data', methods=['GET'])
    @sync
    async def stock_full_data():
        code = request.args.get('code')
        try:
            stock_data = await fetch_merged_stock_data(code, redis_client_stock)
            if stock_data:
                redis_client_stock.setex(f'stock_full_data:{code}', CACHE_DURATION, json.dumps(stock_data))
                return jsonify(stock_data)
            return jsonify({"error": "Failed to fetch stock details"}), 500
        except Exception as e:
            app.logger.error(f"Error fetching stock details: {e}", exc_info=True)
            return jsonify({"error": "Failed to fetch stock details"}), 500

    @app.route('/stock_kr_detail', methods=['GET', 'POST'])
    def stock_kr_detail():
        code = request.args.get('code')

        kakao_id = request.cookies.get('kakao_id')

        if not kakao_id:
            return redirect(url_for('login'))  # Config의 login 라우트 사용

        if request.method == 'POST':
            data = request.json
            stock_symbol = data.get('stock_symbol')
            order_type = data.get('order_type')
            quantity = int(data.get('quantity'))
            target_price = float(data.get('target_price'))

            try:
                # 사용자 데이터 가져오기
                user_data = redis_client_user.get(f'session:{kakao_id}')
                if not user_data:
                    return jsonify({"error": "User not found"}), 404
                
                user_data = json.loads(user_data)
                user_balance = user_data.get('seed_krw', 0)

                # 주식 데이터 가져오기
                stock_data = redis_client_stock.get(f'stock_data:{stock_symbol}')
                if stock_data is None:
                    logger.warning(f"Stock data not found in Redis for stock_symbol: {stock_symbol}")
                    return jsonify({"error": "Stock data not found"}), 404

                stock_data = json.loads(stock_data)
                current_price = stock_data['price']

                # 주문 가능 여부 확인
                if order_type == 'BUY':
                    total_cost = quantity * target_price
                    if total_cost > user_balance:
                        return jsonify({"error": "잔금이 부족합니다"}), 400
                elif order_type == 'SELL':
                    # 포트폴리오 서비스에서 보유 주식 수량 확인 (API 호출 필요)
                    portfolio_response = requests.get(f"{current_config.PORTFOLIO_SERVICE_URL}/api/portfolio/{kakao_id}/{stock_symbol}")
                    portfolio_response.raise_for_status()  # HTTP 에러 발생 시 예외 발생

                    if portfolio_response.status_code == 200:
                        portfolio_data = portfolio_response.json()
                        if portfolio_data['stock_amount'] < quantity:
                            return jsonify({"error": "보유 수량을 초과했습니다", "showAlert": True}), 400
                    elif portfolio_response.status_code == 404:
                        return jsonify({"error": "해당 주식을 보유하고 있지 않습니다", "showAlert": True}), 400
                    else:
                        logger.error(f"Failed to fetch portfolio data. Status code: {portfolio_response.status_code}, content: {portfolio_response.content}")
                        return jsonify({"error": "포트폴리오 데이터 조회 실패"}), 500

                # 주문 내역 생성
                order_data = {
                    'kakao_id': kakao_id,
                    'stock_symbol': stock_symbol,
                    'stock_name': stock_data['name'],
                    'order_type': order_type,
                    'quantity': quantity,
                    'target_price': target_price
                }

                # Kafka로 주문 내역 전송
                try:
                    producer.send('orders_topic', value=order_data)
                    producer.flush()
                    logging.info(f"Kafka message sent successfully: {order_data}")  # 로그 추가
                except Exception as e:
                    logging.error(f"Failed to send Kafka message: {e}")
                    return jsonify({"error": "Failed to process order"}), 500

                # 주문 성공 시 Socket.IO를 통해 주문 내역 업데이트
                socketio.emit('order_update', {
                    'date': datetime.now().strftime('%H:%M'),  # 시:분 형식으로 변경
                    'type': order_type,
                    'quantity': quantity,
                    'price': target_price
                }, room=kakao_id, namespace='/stock')

                return jsonify({"message": "주문이 성공적으로 처리되었습니다.", "status": "success"}), 200

            except requests.exceptions.RequestException as e:
                logger.error(f"포트폴리오 서비스 연결 실패: {e}", exc_info=True)
                return jsonify({"error": "포트폴리오 서비스 연결 실패"}), 500
            except Exception as e:
                logger.error(f"주문 처리 중 오류 발생: {e}", exc_info=True)
                return jsonify({"error": str(e)}), 500

        return render_template('stock_kr_detail.html', code=code, config=current_config)  # ✅ config 전달
    
    @app.route('/healthz', methods=['GET'])
    def health_check():
        """Liveness Probe - 컨테이너가 정상적으로 실행 중인지 확인"""
        return jsonify({"status": "ok"}), 200

    return app

async def preload_stock_data(redis_client, fetch_all_stock_data, cache_duration):
    logging.info("Starting to preload stock data...")
    try:
        stock_data_list = await fetch_all_stock_data(redis_client)
        if stock_data_list:
            logging.info("Saving initial stock data to Redis")
            redis_client.setex('realtime_stock_data', cache_duration, json.dumps(stock_data_list))
            logging.info("Initial data load complete")
        else:
            logging.error("Failed to fetch initial stock data: empty list")
    except Exception as e:
        logging.error(f"Failed to load initial data: {e}")

async def update_stock_data(redis_client, fetch_all_stock_data, cache_duration):
    logging.info("Starting stock data update loop")
    while True:
        try:
            logging.info("Fetching updated stock data...")
            stock_data_list = await fetch_all_stock_data(redis_client)
            if stock_data_list:
                logging.info("Updating Redis with new stock data using transaction")

                with redis_client.pipeline() as pipe:
                    pipe.multi()  # 🔹 트랜잭션 시작
                    pipe.setex('realtime_stock_data', cache_duration, json.dumps(stock_data_list))
                    pipe.execute()  # 🔹 트랜잭션 실행
                
                logging.info("Redis update successful with transaction")
            else:
                logging.error("Stock data update failed: empty list")
        except Exception as e:
            logging.error(f"Stock data update error: {e}")
        await asyncio.sleep(10)

if __name__ == "__main__":
    app = create_app()
    background_tasks = BackgroundTasks()
    
    redis_client_stock = app.config['REDIS_CLIENT_STOCK']
    redis_client_user = app.config['REDIS_CLIENT_USER']
    
    # 주식 데이터는 redis_client_stock을 사용하고, 세션 관리나 사용자 데이터는 redis_client_user 사용
    background_tasks.start(redis_client_stock, fetch_all_stock_data, CACHE_DURATION)  # 주식 데이터 관련 Redis 클라이언트 사용
    logging.info("Starting main application")
    
    try:
        socketio.run(app, debug=True, host="0.0.0.0", port=8002, use_reloader=False)
    except KeyboardInterrupt:
        logging.info("Application shutdown requested")
        background_tasks.stop()
    except Exception as e:
        logging.error(f"Application error: {e}")
    finally:
        logging.info("Application shutdown complete")