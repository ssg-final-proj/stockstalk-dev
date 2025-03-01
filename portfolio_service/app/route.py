import os
import logging
import json
import redis
from flask import Blueprint, render_template, jsonify, request
from sqlalchemy.exc import SQLAlchemyError
from db import db, User, Order, Portfolio, Stock
from datetime import datetime, date
from pytz import timezone

# 로그 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis 클라이언트 설정
redis_client_stock = redis.StrictRedis(host=os.getenv('REDIS_HOST'), port=6379, db=0, decode_responses=True)
redis_client_user = redis.StrictRedis(host=os.getenv('REDIS_HOST'), port=int(os.getenv('REDIS_PORT', 6379)), db=1, decode_responses=True)
redis_client_lock = redis.StrictRedis(host=os.getenv('REDIS_HOST'), port=int(os.getenv('REDIS_PORT', 6379)), db=2, decode_responses=True)
redis_client_profit = redis.StrictRedis(host=os.getenv('REDIS_HOST'), port=int(os.getenv('REDIS_PORT', 6379)), db=3, decode_responses=True)

# 블루프린트 생성
portfolio = Blueprint("portfolio", __name__)

def get_user_from_redis(kakao_id):
    """Redis에서 사용자 정보 가져오기"""
    user_data = redis_client_user.get(f'session:{kakao_id}')
    if user_data:
        return json.loads(user_data)
    return None

def get_user_portfolio_and_orders(kakao_id):
    """사용자의 포트폴리오와 주문 정보 조회"""
    user_data = get_user_from_redis(kakao_id)
    if not user_data:
        return None, None, None

    try:
        with db.session() as session:
            portfolio = session.query(Portfolio, Stock.stock_name).join(
                Stock, Portfolio.stock_symbol == Stock.stock_symbol
            ).filter(Portfolio.kakao_id == kakao_id).all()

            today_orders = session.query(Order, Stock.stock_name).join(
                Stock, Order.stock_symbol == Stock.stock_symbol
            ).filter(
                Order.kakao_id == kakao_id,
                Order.created_at >= datetime.combine(date.today(), datetime.min.time())
            ).all()

            return user_data, portfolio, today_orders
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_user_portfolio_and_orders: {str(e)}")
        return None, None, None

@portfolio.route("/", methods=["GET"])
def mypage():
    kakao_id = request.cookies.get('kakao_id')
    if not kakao_id:
        return render_template("mypage.html", error="로그인이 필요합니다.")

    user_data, portfolio, today_orders = get_user_portfolio_and_orders(kakao_id)
    if not user_data:
        return render_template("mypage.html", error="로그인이 필요합니다.")

    # Redis에서 실시간 수익률 가져오기
    for item, stock_name in portfolio:
        profit_rate = redis_client_profit.get(f'profit_rate:{kakao_id}:{item.stock_symbol}')
        if profit_rate:
            item.real_time_profit_rate = float(profit_rate)
        else:
            item.real_time_profit_rate = item.profit_rate
            
    KST = timezone('Asia/Seoul')
    
    return render_template(
        "mypage.html",
        user=user_data,
        portfolio=portfolio,
        today_orders=today_orders,
        KST=KST
    )


@portfolio.route("/api/order-history", methods=["GET"])
def order_history():
    stock_symbol = request.args.get('code')
    kakao_id = request.cookies.get('kakao_id') or request.args.get('kakao_id')
    if not stock_symbol or not kakao_id:
        return jsonify({"error": "Stock code and login are required"}), 400
    
    try:
        with db.session() as session:
            stock = session.query(Stock).filter_by(stock_symbol=stock_symbol).first()
            if not stock:
                logger.warning(f"Stock not found for stock_code: {stock_symbol}")
                return jsonify([]), 200  # 빈 리스트 반환
            
            orders = session.query(Order).filter_by(stock_symbol=stock_symbol, kakao_id=kakao_id).all()
            if not orders:
                return jsonify([]), 200  # 빈 리스트 반환
            
            order_list = [{
                "date": order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                "type": order.order_type,
                "quantity": order.quantity,
                "price": order.target_price,
                "stock_name": stock.stock_name,
                "status": order.status
            } for order in orders]
            
            return jsonify(order_list), 200
    except SQLAlchemyError as e:
        logger.error(f"Database error in order_history: {str(e)}", exc_info=True)
        return jsonify({"error": "데이터베이스 오류가 발생했습니다."}), 500
    except Exception as e:
        logger.error(f"Unexpected error in order_history: {str(e)}", exc_info=True)
        return jsonify({"error": "예기치 않은 오류가 발생했습니다."}), 500

@portfolio.route("/api/mypage", methods=["GET"])
def mypage_api():
    kakao_id = request.cookies.get('kakao_id')
    logger.info(f"✅ mypage_api 쿠키에서 kakao_id 확인: {kakao_id}")

    if not kakao_id:
        return jsonify({"error": "로그인이 필요합니다."}), 401

    user_data, portfolio, today_orders = get_user_portfolio_and_orders(kakao_id)
    if not user_data:
        return jsonify({"error": "사용자를 찾을 수 없습니다."}), 404

    return jsonify({
        "user": user_data,
        "portfolio": [
            {
                "stock_symbol": p.Portfolio.stock_symbol,
                "stock_name": p.stock_name,
                "quantity": p.Portfolio.stock_amount,
                "total_value": p.Portfolio.total_value,
                "initial_investment": p.Portfolio.initial_investment,
                "profit_rate": p.Portfolio.profit_rate
            }
            for p in portfolio
        ],
        "today_orders": [
            {
                "order_id": order.Order.id,  # 주문 ID 추가
                "stock_symbol": order.Order.stock_symbol,
                "stock_name": order.stock_name,
                "order_type": order.Order.order_type,
                "target_price": order.Order.target_price,
                "quantity": order.Order.quantity,
                "status": order.Order.status,
                "created_at": order.Order.created_at.astimezone(timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')  # KST로 변경
            }
            for order in today_orders
        ]
    })

def update_user_data(kakao_id, new_data):
    """Redis와 데이터베이스의 사용자 데이터 동기화"""
    try:
        with db.session() as session:
            user = session.query(User).filter_by(kakao_id=kakao_id).first()
            if user:
                for key, value in new_data.items():
                    setattr(user, key, value)
                session.commit()

                # 기존 Redis 데이터 불러오기
                existing_data = redis_client_user.get(f'session:{kakao_id}')
                if existing_data:
                    existing_data = json.loads(existing_data)
                    existing_data.update(new_data)
                else:
                    existing_data = new_data

                # Redis 업데이트
                redis_client_user.set(f'session:{kakao_id}', json.dumps(existing_data), ex=86400)
                logger.info(f"User data updated for kakao_id: {kakao_id}")
            else:
                logger.warning(f"User not found for kakao_id: {kakao_id}")
    except SQLAlchemyError as e:
        logger.error(f"Database error in update_user_data: {str(e)}")

@portfolio.route("/api/cancel-order", methods=["POST"])
def cancel_order():
    data = request.get_json()
    order_id = data.get('order_id')
    kakao_id = request.cookies.get('kakao_id')

    logger.info(f"Attempting to cancel order. order_id: {order_id}, kakao_id: {kakao_id}") # 로그 추가

    if not order_id or not kakao_id:
        logger.warning(f"Missing order_id or kakao_id. order_id: {order_id}, kakao_id: {kakao_id}")
        return jsonify({"error": "주문 ID와 로그인이 필요합니다."}), 400

    try:
        with db.session() as session:
            order = session.query(Order).filter(Order.id == order_id, Order.kakao_id == kakao_id, Order.status == 'PENDING').first()
            if not order:
                logger.warning(f"Order not found or not PENDING. order_id: {order_id}, kakao_id: {kakao_id}")
                return jsonify({"error": "취소할 주문을 찾을 수 없습니다."}), 404

            order.status = 'CANCELLED'
            session.commit()
            logger.info(f"Order cancelled successfully. order_id: {order_id}, kakao_id: {kakao_id}")
            return jsonify({"message": "주문이 취소되었습니다.", "order_id": order_id}), 200

    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Database error in cancel_order: {str(e)}, order_id: {order_id}, kakao_id: {kakao_id}", exc_info=True)
        return jsonify({"error": "데이터베이스 오류가 발생했습니다."}), 500
    except Exception as e:
        logger.error(f"Unexpected error in cancel_order: {str(e)}, order_id: {order_id}, kakao_id: {kakao_id}", exc_info=True)
        return jsonify({"error": "예기치 않은 오류가 발생했습니다."}), 500
