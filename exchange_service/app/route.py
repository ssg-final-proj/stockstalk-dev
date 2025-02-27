# route.py (exchange_service)
import os
import json
import logging
import redis
import yfinance as yf
import requests
from flask import Blueprint, request, jsonify, render_template
from db import db, Exchange
from datetime import datetime, timedelta

# 캐시된 환율 데이터를 저장할 변수
cached_exchange_rate = None
last_fetch_time = None

# 로그 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis 클라이언트 설정
redis_client_user = redis.StrictRedis(host="redis", port=6379, db=1, decode_responses=True)

# 블루프린트 생성
exchange = Blueprint("exchange", __name__)

def get_user_from_redis(kakao_id):
    """Redis에서 사용자 정보 가져오기"""
    user_data = redis_client_user.get(f'session:{kakao_id}')
    if user_data:
        return json.loads(user_data)
    return None

def get_exchange_rate():
    """실시간 환율 정보를 가져오고 캐싱"""
    global cached_exchange_rate, last_fetch_time
    now = datetime.now()
    next_full_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    if cached_exchange_rate and last_fetch_time and last_fetch_time >= next_full_hour - timedelta(hours=1):
        logger.info(f"✅ 캐시된 환율 사용: {cached_exchange_rate}")
        return cached_exchange_rate
    
    try:
        ticker = yf.Ticker("USDKRW=X")
        exchange_rate = ticker.history(period="1d")['Close'].iloc[-1]
        cached_exchange_rate = round(exchange_rate, 2)
        last_fetch_time = now
        logger.info(f"📡 실시간 환율 조회 성공: {cached_exchange_rate}")
        return cached_exchange_rate
    except Exception as e:
        logger.error(f"❌ 환율 데이터를 가져오는 중 오류 발생: {e}")
        return None

@exchange.route('/', methods=['GET', 'POST'])
def handle_exchange():
    """환전 처리 및 화면 렌더링"""
    kakao_id = request.cookies.get('kakao_id')
    logger.info(f"✅ exchange 쿠키에서 kakao_id 확인: {kakao_id}")

    if not kakao_id:
        return render_template("exchange.html", error="로그인이 필요합니다.")

    user_data = get_user_from_redis(kakao_id)
    if not user_data:
        return render_template("exchange.html", error="로그인이 필요합니다.")

    exchange_rate = get_exchange_rate() or 1450.00
    message = ""

    if request.method == 'POST':
        try:
            currency_pair = request.form.get('currency_pair')
            amount = float(request.form.get('amount', 0))
            kakao_id = user_data['kakao_id']

            # 트랜잭션 시작
            db.session.begin_nested()

            if currency_pair == 'KRW_to_USD' and user_data['seed_krw'] >= amount:
                exchanged_amount = round(amount / exchange_rate, 2)
                new_krw = user_data['seed_krw'] - amount
                new_usd = user_data['seed_usd'] + exchanged_amount
                
                # DB 업데이트
                db.session.add(Exchange(
                    kakao_id=kakao_id,
                    from_currency='KRW',
                    to_currency='USD',
                    amount=amount,
                    exchange_rate=exchange_rate,
                    total_value=exchanged_amount
                ))

                # Redis 업데이트
                user_data['seed_krw'] = new_krw
                user_data['seed_usd'] = new_usd
                redis_client_user.set(f'session:{kakao_id}', json.dumps(user_data), ex=86400)

                message = f"{amount} KRW를 {exchanged_amount} USD로 환전했습니다!"

            elif currency_pair == 'USD_to_KRW' and user_data['seed_usd'] >= amount:
                exchanged_amount = round(amount * exchange_rate, 2)
                new_usd = user_data['seed_usd'] - amount
                new_krw = user_data['seed_krw'] + exchanged_amount

                # DB 업데이트
                db.session.add(Exchange(
                    kakao_id=kakao_id,
                    from_currency='USD',
                    to_currency='KRW',
                    amount=amount,
                    exchange_rate=exchange_rate,
                    total_value=exchanged_amount
                ))

                # Redis 업데이트
                user_data['seed_krw'] = new_krw
                user_data['seed_usd'] = new_usd
                redis_client_user.set(f'session:{kakao_id}', json.dumps(user_data), ex=86400)

                message = f"{amount} USD를 {exchanged_amount} KRW로 환전했습니다!"
            else:
                message = "잔액이 부족하거나 올바른 통화를 선택해주세요."
                return render_template('exchange.html', exchange_rate=exchange_rate, message=message)

            # auth_service에 업데이트 요청
            try:
                update_url = "http://auth_service:8001/auth/api/update_user"
                response = requests.post(update_url, json={
                    "kakao_id": kakao_id,
                    "seed_krw": user_data['seed_krw'],
                    "seed_usd": user_data['seed_usd']
                })
                
                if response.status_code != 200:
                    logger.error(f"❌ Auth service 업데이트 실패: {response.text}")
                    raise Exception("Auth service update failed")
                
                logger.info("✅ Auth service 업데이트 성공")
                
                # 모든 작업이 성공하면 트랜잭션 커밋
                db.session.commit()
            except Exception as e:
                # 실패시 롤백
                db.session.rollback()
                logger.error(f"❌ 환전 처리 중 오류 발생: {str(e)}")
                message = "환전 처리 중 오류가 발생했습니다."
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ 환전 처리 중 오류 발생: {str(e)}")
            message = "환전 처리 중 오류가 발생했습니다."

    return render_template('exchange.html', user=user_data, exchange_rate=exchange_rate, message=message)


@exchange.route('/get_balance', methods=['POST'])
def get_balance():
    """사용자의 KRW/USD 잔액 조회 API"""
    kakao_id = request.cookies.get('kakao_id')
    logger.info(f"✅ mypage 쿠키에서 kakao_id 확인: {kakao_id}")

    if not kakao_id:
        return render_template("exchange.html", error="로그인이 필요합니다.")

    user_data = get_user_from_redis(kakao_id)
    if not user_data:
        return render_template("exchange.html", error="로그인이 필요합니다.")

    # User 정보를 Redis에서 가져와 변수에 할당
    seed_krw = user_data['seed_krw']
    seed_usd = user_data['seed_usd']

    currency_pair = request.json.get('currency_pair')
    balance = seed_krw if currency_pair == 'KRW_to_USD' else seed_usd if currency_pair == 'USD_to_KRW' else 0

    return jsonify({'balance': balance})
