from flask import Blueprint, render_template, session, redirect, request, url_for, jsonify, make_response
from datetime import datetime, timezone
from db import db, User
from config import current_config
import requests
import logging
import json
import redis

auth = Blueprint("auth", __name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ Config에서 서비스 URL 직접 로드
AUTH_SERVICE_URL = current_config.AUTH_SERVICE_URL
PORTFOLIO_SERVICE_URL = current_config.PORTFOLIO_SERVICE_URL
EXCHANGE_SERVICE_URL = current_config.EXCHANGE_SERVICE_URL
STOCK_SERVICE_URL = current_config.BASE_URL

# Redis 설정
redis_client_user = redis.StrictRedis(
    host=current_config.REDIS_HOST,
    port=current_config.REDIS_PORT,
    db=1,
    decode_responses=True
)

@auth.route("/", methods=["GET"])
def kakaologin():
    kakao_id = request.cookies.get("kakao_id")
    
    if kakao_id and redis_client_user.exists(f"session:{kakao_id}"):
        user_data = json.loads(redis_client_user.get(f"session:{kakao_id}"))
        if user_data.get("username") == "No username":
            return redirect(url_for('auth.set_username'))
        return redirect(STOCK_SERVICE_URL)  # stock-kr-service로 리다이렉트
    return render_template("auth.html", service_urls={
        'auth': AUTH_SERVICE_URL,
        'portfolio': PORTFOLIO_SERVICE_URL,
        'exchange': EXCHANGE_SERVICE_URL,
        'home': STOCK_SERVICE_URL  # 홈 URL 추가
    })

@auth.route("/kakaoLoginLogic", methods=["GET"])
def kakaoLoginLogic():
    redirect_uri = f"{AUTH_SERVICE_URL}/kakaoLoginLogicRedirect"
    url = f"https://kauth.kakao.com/oauth/authorize?client_id={current_config.REST_API_KEY}&redirect_uri={redirect_uri}&response_type=code"
    return redirect(url)

@auth.route("/kakaoLoginLogicRedirect", methods=["GET"])
def kakaoLoginLogicRedirect():
    code = request.args.get("code")
    if not code:
        return "인증 코드 누락", 400

    token_response = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": current_config.REST_API_KEY, # ✅ REST API KEY 사용
            "redirect_uri": f"{AUTH_SERVICE_URL}/kakaoLoginLogicRedirect",
            "code": code,
        },
    )

    if token_response.status_code != 200:
        logger.error(f"토큰 요청 실패: {token_response.text}")
        return "토큰 발급 실패", 500

    access_token = token_response.json().get("access_token")
    if not access_token:
        return "Access token 발급 실패.", 500

    kakao_user_info = requests.get(
        "https://kapi.kakao.com/v2/user/me",
        headers={"Authorization": f"Bearer {access_token}"},
    ).json()

    if not kakao_user_info:
        return "카카오 사용자 정보 획득 실패", 500

    kakao_id = str(kakao_user_info.get("id"))
    username = kakao_user_info.get("properties", {}).get("nickname", "No username")
    email = kakao_user_info.get("kakao_account", {}).get("email")

    user_to_store = User.query.filter_by(kakao_id=kakao_id).first()

    if not user_to_store:
        try:
            user_to_store = User(
                kakao_id=kakao_id,
                username=username,
                email=email,
                seed_krw=1000000.0,
                seed_usd=0.0,
                created_at=datetime.now(timezone.utc),
                last_login=datetime.now(timezone.utc),
            )
            db.session.add(user_to_store)
            db.session.commit()
            db.session.refresh(user_to_store)
        except Exception as e:
            db.session.rollback()
            logger.error(f"DB INSERT ERROR: {e}")
            return "DB 오류 발생", 500
    else:
        try:
            user_to_store.last_login = datetime.now(timezone.utc)
            if not user_to_store.email and email:
                user_to_store.email = email
            db.session.commit()
            db.session.refresh(user_to_store)
        except Exception as e:
            db.session.rollback()
            logger.error(f"DB UPDATE ERROR: {e}")
            return "DB 업데이트 오류 발생", 500

    user_data = {
        "id": user_to_store.id,
        "kakao_id": user_to_store.kakao_id,
        "username": user_to_store.username,
        "email": user_to_store.email,
        "seed_krw": user_to_store.seed_krw,
        "seed_usd": user_to_store.seed_usd,
        "last_login": user_to_store.last_login.isoformat(),
    }
    
    try:
        redis_client_user.set(f"session:{user_to_store.kakao_id}", json.dumps(user_data), ex=86400)

        # 쿠키 설정
        response = make_response(redirect(STOCK_SERVICE_URL))

        response.set_cookie(
            "kakao_id",
            value=str(user_to_store.kakao_id),
            max_age=86400,
            domain=".stockstalk.store",  # 모든 서브도메인 적용
            secure=True,                # HTTPS 필수
            samesite="None",            # 크로스 사이트 허용
            path="/",                   # 전체 경로 적용
            httponly=False
        )

        if user_data["username"] == "No username":
            response = redirect(url_for('auth.set_username'))  # 닉네임 설정 페이지로 리다이렉트
        else:
            response = redirect(STOCK_SERVICE_URL)  # stock-kr-service로 리다이렉트

        logger.info(f"쿠키 설정 완료: {user_to_store.kakao_id}")
        return response

    except Exception as e:
        logger.error(f"Redis 또는 쿠키 설정 오류: {e}")
        return "Redis 또는 쿠키 설정 오류 발생", 500

@auth.route("/set_username", methods=["GET", "POST"])
def set_username():
    kakao_id = request.cookies.get("kakao_id")
    if not kakao_id:
        return redirect(url_for("auth.kakaologin"))

    user = User.query.filter_by(kakao_id=kakao_id).first()
    if not user:
        return redirect(url_for("auth.kakaologin"))

    if request.method == "POST":
        new_username = request.form.get("username")
        if new_username:
            user.username = new_username
            db.session.commit()

            user_data = {
                "id": user.id,
                "kakao_id": user.kakao_id,
                "username": user.username,
                "email": user.email,
                "seed_krw": user.seed_krw,
                "seed_usd": user.seed_usd,
                "last_login": user.last_login.isoformat() if user.last_login else None,
            }
            redis_client_user.set(f"session:{kakao_id}", json.dumps(user_data), ex=86400)

            return redirect(STOCK_SERVICE_URL)

    return render_template("set_username.html",
                           user=user_data,
                           service_urls={
                               'home': STOCK_SERVICE_URL,
                               'portfolio': PORTFOLIO_SERVICE_URL
                           })

@auth.route("/check_nickname", methods=["GET"])
def check_nickname():
    username = request.args.get("username", "").strip()
    if not username:
        return jsonify({"exists": False})

    existing_user = User.query.filter_by(username=username).first()
    return jsonify({"exists": bool(existing_user)})

@auth.route("/logout", methods=["GET"])
def logout():
    kakao_id = request.cookies.get("kakao_id")

    if kakao_id and redis_client_user.exists(f"session:{kakao_id}"):
        redis_client_user.delete(f"session:{kakao_id}")

    response = make_response(redirect(STOCK_SERVICE_URL))
    response.delete_cookie("kakao_id", path='/', domain=".stockstalk.store")  # 쿠키 삭제 시 path 지정
    return response

@auth.route("/check-login", methods=["GET"])
def check_login():
    kakao_id = request.cookies.get("kakao_id")
    logger.info(f"[DEBUG] 쿠키에서 추출한 kakao_id: {kakao_id}")
    
    if not kakao_id:
        logger.warning("쿠키에 kakao_id 없음")
        return jsonify({"loggedIn": False})

    try:
        user_data = redis_client_user.get(f"session:{kakao_id}")
        logger.info(f"[DEBUG] Redis에서 조회한 사용자 데이터: {user_data}")
        if user_data:
            return jsonify({"loggedIn": True, "userData": json.loads(user_data)})
        return jsonify({"loggedIn": False})
    except Exception as e:
        logger.error(f"[ERROR] 로그인 확인 실패: {str(e)}")
        return jsonify({"error": str(e)}), 500


@auth.route('/api/update_user', methods=['POST'])
def update_user():
    try:
        data = request.get_json()
        kakao_id = data.get('kakao_id')
        seed_krw = data.get('seed_krw')
        seed_usd = data.get('seed_usd')

        if not all([kakao_id, seed_krw is not None, seed_usd is not None]):
            return jsonify({"error": "Missing required fields"}), 400

        user = User.query.filter_by(kakao_id=kakao_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        # DB 업데이트
        user.seed_krw = seed_krw
        user.seed_usd = data['seed_usd']
        db.session.commit()

        # Redis 업데이트
        user_data = json.loads(redis_client_user.get(f'session:{kakao_id}'))
        if user_data:
            user_data['seed_krw'] = seed_krw
            user_data['seed_usd'] = seed_usd
            redis_client_user.set(f'session:{kakao_id}', json.dumps(user_data), ex=86400)
            return jsonify({"message": "User updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500