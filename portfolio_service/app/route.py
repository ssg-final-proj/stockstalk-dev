import os
import logging
import json
import redis
from flask import Blueprint, render_template, jsonify, request
from sqlalchemy.sql import text
from sqlalchemy.exc import SQLAlchemyError
from db import db, User, Order, Portfolio, Stock
from datetime import datetime, date
from pytz import timezone
from config import current_config  # Config import 추가

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

redis_client_stock = redis.StrictRedis(host=os.getenv("REDIS_HOST"), port=6379, db=0, decode_responses=True)
redis_client_user = redis.StrictRedis(host=os.getenv("REDIS_HOST"), port=int(os.getenv("REDIS_PORT", 6379)), db=1, decode_responses=True)
redis_client_lock = redis.StrictRedis(host=os.getenv("REDIS_HOST"), port=int(os.getenv("REDIS_PORT", 6379)), db=2, decode_responses=True)
redis_client_profit = redis.StrictRedis(host=os.getenv("REDIS_HOST"), port=int(os.getenv("REDIS_PORT", 6379)), db=3, decode_responses=True)

portfolio = Blueprint(
    'portfolio',
    __name__,
    static_folder='static',
    static_url_path='/portfolio/static'
)

# Config에서 서비스 URL 직접 로드
STOCK_SERVICE_URL = current_config.BASE_URL
AUTH_SERVICE_URL = current_config.AUTH_SERVICE_URL
EXCHANGE_SERVICE_URL = current_config.EXCHANGE_SERVICE_URL
PORTFOLIO_SERVICE_URL = current_config.PORTFOLIO_SERVICE_URL

def get_user_from_redis(kakao_id):
    user_data = redis_client_user.get(f"session:{kakao_id}")
    if user_data:
        return json.loads(user_data)
    return None

def get_user_portfolio_and_orders(kakao_id):
    user_data = get_user_from_redis(kakao_id)
    if not user_data:
        return None, None, None

    try:
        with db.session() as session:
            portfolio = (
                session.query(Portfolio, Stock.stock_name)
                .join(Stock, Portfolio.stock_symbol == Stock.stock_symbol)
                .filter(Portfolio.kakao_id == kakao_id)
                .all()
            )

            today_orders = (
                session.query(Order, Stock.stock_name)
                .join(Stock, Order.stock_symbol == Stock.stock_symbol)
                .filter(
                    Order.kakao_id == kakao_id,
                    Order.created_at >= datetime.combine(date.today(), datetime.min.time()),
                )
                .all()
            )

            return user_data, portfolio, today_orders
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_user_portfolio_and_orders: {str(e)}")
        return None, None, None

@portfolio.route("/", methods=["GET"])
def mypage():
    kakao_id = request.cookies.get("kakao_id")
    if not kakao_id:
        return render_template(
            "mypage.html",
            error="로그인이 필요합니다.",
            service_urls={
                'home': STOCK_SERVICE_URL,
                'auth': AUTH_SERVICE_URL,
                'exchange': EXCHANGE_SERVICE_URL,
                'portfolio': PORTFOLIO_SERVICE_URL
            }
        )

    user_data, portfolio, today_orders = get_user_portfolio_and_orders(kakao_id)
    if not user_data:
        return render_template(
            "mypage.html",
            error="로그인이 필요합니다.",
            service_urls={
                'home': STOCK_SERVICE_URL,
                'auth': AUTH_SERVICE_URL,
                'exchange': EXCHANGE_SERVICE_URL,
                'portfolio': PORTFOLIO_SERVICE_URL
            }
        )

    try:
        with db.session() as session:
            query = text(
                """
                SELECT profit_rate_total, p_rank
                FROM portfolio_db.portfolio_ranking
                WHERE kakao_id = :kakao_id
            """
            )
            result = session.execute(query, {"kakao_id": kakao_id}).fetchone()

            if result:
                profit_rate_total, p_rank = result
                profit_rate_total = round(float(profit_rate_total), 2) if profit_rate_total is not None else 0.0
                p_rank = int(p_rank) if p_rank is not None else None
            else:
                profit_rate_total, p_rank = 0.0, None

    except SQLAlchemyError as e:
        logger.error(f"❌ Database error in mypage: {str(e)}")
        profit_rate_total, p_rank = 0.0, None

    for item, stock_name in portfolio:
        profit_rate = redis_client_profit.get(f"profit_rate:{kakao_id}:{item.stock_symbol}")
        if profit_rate:
            item.real_time_profit_rate = float(profit_rate)
        else:
            item.real_time_profit_rate = item.profit_rate

    KST = timezone("Asia/Seoul")

    return render_template(
        "mypage.html",
        user=user_data,
        portfolio=portfolio,
        today_orders=today_orders,
        profit_rate_total=profit_rate_total,
        p_rank=p_rank,
        KST=KST,
        service_urls={
            'home': STOCK_SERVICE_URL,
            'auth': AUTH_SERVICE_URL,
            'exchange': EXCHANGE_SERVICE_URL,
            'portfolio': PORTFOLIO_SERVICE_URL
        }
    )

@portfolio.route("/api/order-history", methods=["GET"])
def order_history():
    stock_symbol = request.args.get("code")
    kakao_id = request.cookies.get("kakao_id") or request.args.get("kakao_id")
    if not stock_symbol or not kakao_id:
        return jsonify({"error": "Stock code and login are required"}), 400

    try:
        with db.session() as session:
            stock = session.query(Stock).filter_by(stock_symbol=stock_symbol).first()
            if not stock:
                logger.warning(f"Stock not found for stock_code: {stock_symbol}")
                return jsonify([]), 200

            orders = session.query(Order).filter_by(stock_symbol=stock_symbol, kakao_id=kakao_id).all()
            if not orders:
                return jsonify([]), 200

            order_list = [
                {
                    "date": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "type": order.order_type,
                    "quantity": order.quantity,
                    "price": order.target_price,
                    "stock_name": stock.stock_name,
                    "status": order.status,
                }
                for order in orders
            ]

            return jsonify(order_list), 200
    except SQLAlchemyError as e:
        logger.error(f"Database error in order_history: {str(e)}", exc_info=True)
        return jsonify({"error": "데이터베이스 오류가 발생했습니다."}), 500
    except Exception as e:
        logger.error(f"Unexpected error in order_history: {str(e)}", exc_info=True)
        return jsonify({"error": "예기치 않은 오류가 발생했습니다."}), 500

@portfolio.route("/api/mypage", methods=["GET"])
def mypage_api():
    kakao_id = request.cookies.get("kakao_id")
    logger.info(f"✅ mypage_api 쿠키에서 kakao_id 확인: {kakao_id}")

    if not kakao_id:
        return jsonify({"error": "로그인이 필요합니다."}), 401

    user_data, portfolio, today_orders = get_user_portfolio_and_orders(kakao_id)
    if not user_data:
        return jsonify({"error": "사용자를 찾을 수 없습니다."}), 404

    try:
        with db.session() as session:
            ranking_data = session.execute(
                text(
                    "SELECT profit_rate_total, p_rank FROM portfolio_db.portfolio_ranking WHERE kakao_id = :kakao_id"
                ),
                {"kakao_id": kakao_id},
            ).fetchone()

            if ranking_data:
                total_profit_rate = round(float(ranking_data[0]), 2) if ranking_data[0] is not None else 0.0
                ranking = int(ranking_data[1]) if ranking_data[1] is not None else None
            else:
                total_profit_rate, ranking = 0.0, None
    except SQLAlchemyError as e:
        logger.error(f"Database error in fetching ranking data: {str(e)}")
        total_profit_rate, ranking = 0.0, None

    return jsonify(
        {
            "user": user_data,
            "total_profit_rate": total_profit_rate,
            "ranking": ranking,
            "portfolio": [
                {
                    "stock_symbol": p.Portfolio.stock_symbol,
                    "stock_name": p.stock_name,
                    "quantity": p.Portfolio.stock_amount,
                    "total_value": p.Portfolio.total_value,
                    "initial_investment": p.Portfolio.initial_investment,
                    "profit_rate": p.Portfolio.profit_rate,
                }
                for p in portfolio
            ],
            "today_orders": [
                {
                    "order_id": order.Order.id,
                    "stock_symbol": order.Order.stock_symbol,
                    "stock_name": order.stock_name,
                    "order_type": order.Order.order_type,
                    "target_price": order.Order.target_price,
                    "quantity": order.Order.quantity,
                    "status": order.Order.status,
                    "created_at": order.Order.created_at.astimezone(timezone("Asia/Seoul")).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                }
                for order in today_orders
            ],
        }
    )

def update_user_data(kakao_id, new_data):
    try:
        with db.session() as session:
            user = session.query(User).filter_by(kakao_id=kakao_id).first()
            if user:
                for key, value in new_data.items():
                    setattr(user, key, value)
                session.commit()

                existing_data = redis_client_user.get(f"session:{kakao_id}")
                if existing_data:
                    existing_data = json.loads(existing_data)
                    existing_data.update(new_data)
                else:
                    existing_data = new_data

                redis_client_user.set(f"session:{kakao_id}", json.dumps(existing_data), ex=86400)
                logger.info(f"User data updated for kakao_id: {kakao_id}")
            else:
                logger.warning(f"User not found for kakao_id: {kakao_id}")
    except SQLAlchemyError as e:
        logger.error(f"Database error in update_user_data: {str(e)}")

@portfolio.route("/api/cancel-order", methods=["POST"])
def cancel_order():
    order_id = request.json.get("order_id")
    kakao_id = request.cookies.get("kakao_id")

    if not order_id or not kakao_id:
        return jsonify({"error": "주문 ID와 로그인이 필요합니다."}), 400

    try:
        with db.session() as session:
            order = session.query(Order).filter_by(id=order_id, kakao_id=kakao_id).first()
            if not order:
                return jsonify({"error": "주문을 찾을 수 없습니다."}), 404

            if order.status != "PENDING":
                return jsonify({"error": "대기 중인 주문만 취소할 수 있습니다."}), 400

            order.status = "CANCELLED"
            session.commit()

            return jsonify({"message": "주문이 성공적으로 취소되었습니다."}), 200
    except SQLAlchemyError as e:
        logger.error(f"Database error in cancel_order: {str(e)}")
        return jsonify({"error": "주문 취소 중 오류가 발생했습니다."}), 500
