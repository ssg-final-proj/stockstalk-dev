import os
import json
import logging
import redis
import yfinance as yf
import requests
from flask import Blueprint, request, jsonify, render_template
from db import db, Exchange
from datetime import datetime, timedelta
from config import current_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

exchange = Blueprint(
    'exchange',
    __name__,
    static_folder='static',
    static_url_path='/exchange/static'
)

redis_client_user = redis.StrictRedis(
    host=current_config.REDIS_HOST,
    port=current_config.REDIS_PORT,
    db=1,
    decode_responses=True
)

redis_client_exchange = redis.StrictRedis(
    host=current_config.REDIS_HOST,
    port=current_config.REDIS_PORT,
    db=5,
    decode_responses=True
)

STOCK_SERVICE_URL = current_config.BASE_URL
AUTH_SERVICE_URL = current_config.AUTH_SERVICE_URL
PORTFOLIO_SERVICE_URL = current_config.PORTFOLIO_SERVICE_URL

def get_user_from_redis(kakao_id):
    user_data = redis_client_user.get(f'session:{kakao_id}')
    return json.loads(user_data) if user_data else None

def get_exchange_rate():
    try:
        cached_rate = redis_client_exchange.get('cached_exchange_rate')
        if cached_rate:
            logger.info(f"✅ Redis 캐시된 환율 사용: {cached_rate}")
            return float(cached_rate)  # 문자열을 float으로 변환

        ticker = yf.Ticker("USDKRW=X")
        exchange_rate = float(ticker.history(period="1d")['Close'].iloc[-1])  # numpy -> Python float
        rounded_rate = round(exchange_rate, 2)

        redis_client_exchange.setex('cached_exchange_rate', timedelta(hours=1), rounded_rate)
        logger.info(f"📡 실시간 환율 조회 성공: {rounded_rate}")
        return rounded_rate
    except Exception as e:
        logger.error(f"❌ 환율 데이터 오류: {str(e)}", exc_info=True)  # 상세 오류 로깅
        return None

@exchange.route('/', methods=['GET', 'POST'])
def handle_exchange():
    kakao_id = request.cookies.get('kakao_id')
    logger.info(f"✅ Exchange 쿠키 확인: {kakao_id}")

    if not kakao_id:
        return render_template("exchange.html", 
                             error="로그인이 필요합니다.",
                             service_urls={
                                 'auth': AUTH_SERVICE_URL,
                                 'portfolio': PORTFOLIO_SERVICE_URL,
                                 'home': STOCK_SERVICE_URL
                             })

    user_data = get_user_from_redis(kakao_id)
    if not user_data:
        return render_template("exchange.html", 
                             error="로그인이 필요합니다.",
                             service_urls={
                                 'auth': AUTH_SERVICE_URL,
                                 'portfolio': PORTFOLIO_SERVICE_URL,
                                 'home': STOCK_SERVICE_URL
                             })

    exchange_rate = get_exchange_rate() or 1450.00
    message = ""

    if request.method == 'POST':
        try:
            currency_pair = request.form.get('currency_pair')
            amount = float(request.form.get('amount', 0))
            
            if currency_pair == 'KRW_to_USD' and user_data['seed_krw'] >= amount:
                exchanged_amount = round(amount / exchange_rate, 2)
                new_krw = user_data['seed_krw'] - amount
                new_usd = user_data['seed_usd'] + exchanged_amount
                
                db.session.add(Exchange(
                    kakao_id=kakao_id,
                    from_currency='KRW',
                    to_currency='USD',
                    amount=amount,
                    exchange_rate=exchange_rate,
                    total_value=exchanged_amount
                ))

                user_data['seed_krw'] = new_krw
                user_data['seed_usd'] = new_usd
                redis_client_user.set(f'session:{kakao_id}', json.dumps(user_data), ex=86400)

                message = f"{amount} KRW를 {exchanged_amount} USD로 환전했습니다!"

            elif currency_pair == 'USD_to_KRW' and user_data['seed_usd'] >= amount:
                exchanged_amount = round(amount * exchange_rate, 2)
                new_usd = user_data['seed_usd'] - amount
                new_krw = user_data['seed_krw'] + exchanged_amount

                db.session.add(Exchange(
                    kakao_id=kakao_id,
                    from_currency='USD',
                    to_currency='KRW',
                    amount=amount,
                    exchange_rate=exchange_rate,
                    total_value=exchanged_amount
                ))

                user_data['seed_krw'] = new_krw
                user_data['seed_usd'] = new_usd
                redis_client_user.set(f'session:{kakao_id}', json.dumps(user_data), ex=86400)

                message = f"{amount} USD를 {exchanged_amount} KRW로 환전했습니다!"
            else:
                message = "잔액이 부족하거나 올바른 통화를 선택해주세요."
                return render_template('exchange.html', 
                                     exchange_rate=exchange_rate, 
                                     message=message,
                                     service_urls={
                                         'auth': AUTH_SERVICE_URL,
                                         'portfolio': PORTFOLIO_SERVICE_URL,
                                         'home': STOCK_SERVICE_URL
                                     })

            update_url = f"{AUTH_SERVICE_URL}/api/update_user"
            response = requests.post(update_url, json={
                "kakao_id": kakao_id,
                "seed_krw": user_data['seed_krw'],
                "seed_usd": user_data['seed_usd']
            })
            
            if response.status_code != 200:
                logger.error(f"❌ Auth service 업데이트 실패: {response.text}")
                raise Exception("Auth service update failed")
            
            logger.info("✅ Auth service 업데이트 성공")
            
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ 환전 처리 중 오류 발생: {str(e)}")
            message = "환전 처리 중 오류가 발생했습니다."

    return render_template('exchange.html',
                         user=user_data,
                         exchange_rate=exchange_rate,
                         message=message,
                         service_urls={
                             'auth': AUTH_SERVICE_URL,
                             'portfolio': PORTFOLIO_SERVICE_URL,
                             'home': STOCK_SERVICE_URL
                         })

@exchange.route('/get_balance', methods=['POST'])
def get_balance():
    try:
        kakao_id = request.cookies.get('kakao_id')
        if not kakao_id:
            return jsonify({"error": "로그인 필요"}), 401  # ✅ JSON 반환

        user_data = get_user_from_redis(kakao_id)
        if not user_data:
            return jsonify({"error": "사용자 정보 없음"}), 404  # ✅ JSON 반환

        currency_pair = request.json.get('currency_pair')
        balance = user_data['seed_krw'] if currency_pair == 'KRW_to_USD' else user_data['seed_usd']
        return jsonify({'balance': balance})  # ✅ JSON 반환
    except Exception as e:
        logger.error(f"❌ 잔액 조회 오류: {str(e)}")
        return jsonify({"error": "서버 내부 오류"}), 500  # ✅ 모든 오류 JSON 처리