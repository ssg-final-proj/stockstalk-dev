from flask import Blueprint, render_template, session, redirect, request, url_for, jsonify, make_response
from datetime import datetime, timezone
from db import db, User
from config import current_config
import requests
import logging
import json
import redis

auth = Blueprint(
    'auth',
    __name__,
    static_folder='static',
    static_url_path='/auth/static'
)

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
    """ 카카오 로그인 처리 후 사용자 정보 Redis에 저장 """
    code = request.args.get("code")
    if not code:
        return "카카오 로그인 인증 코드가 없습니다.", 400

    # 카카오에서 액세스 토큰 가져오기
    response = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": current_config.REST_API_KEY, # ✅ REST API KEY 사용
            "redirect_uri": f"{AUTH_SERVICE_URL}/kakaoLoginLogicRedirect",
            "code": code,
        },
    )

    access_token = response.json().get("access_token")
    if not access_token:
        return "Access token 발급 실패.", 500

    # 카카오에서 사용자 정보 가져오기
    kakao_user_info = requests.get(
        "https://kapi.kakao.com/v2/user/me",
        headers={"Authorization": f"Bearer {access_token}"},
    ).json()

    kakao_id = kakao_user_info.get("id")
    username = kakao_user_info.get("properties", {}).get("nickname", "No username")
    email = kakao_user_info.get("kakao_account", {}).get("email")

    # 데이터베이스에서 사용자 확인
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
            print(f"❌ DB INSERT ERROR: {e}")
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
            print(f"❌ DB UPDATE ERROR: {e}")
            return "DB 업데이트 오류 발생", 500

    # Redis에 전체 사용자 데이터 저장
    user_data = {
        "id": user_to_store.id,
        "kakao_id": user_to_store.kakao_id,
        "username": user_to_store.username,
        "email": user_to_store.email,
        "seed_krw": user_to_store.seed_krw,
        "seed_usd": user_to_store.seed_usd,
        "last_login": user_to_store.last_login.isoformat(),
    }
    redis_client_user.set(f"session:{user_to_store.kakao_id}", json.dumps(user_data), ex=86400)

    # 쿠키에 kakao_id 저장 및 리다이렉트
    if user_data["username"] == "No username":
        redirect_url = url_for('auth.set_username')
    else:
        redirect_url = STOCK_SERVICE_URL

    response = make_response(redirect(redirect_url))
    response.set_cookie(
        "kakao_id",
        value=str(user_to_store.kakao_id),
        domain=".stockstalk.store",
        max_age=86400,
        secure=True,
        samesite="Lax",
        path="/",
    )
    print(f"✅ 쿠키 설정 완료: {user_to_store.kakao_id}")
    return response

@auth.route("/set_username", methods=["GET", "POST"])
def set_username():
    """ 사용자 닉네임 설정 """
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

            # Redis 업데이트
            user_data = redis_client_user.get(f"session:{kakao_id}")
            if user_data:
                user_data = json.loads(user_data)
                user_data["username"] = new_username
                redis_client_user.set(f"session:{kakao_id}", json.dumps(user_data), ex=86400)

            return redirect(STOCK_SERVICE_URL)

    return render_template("set_username.html")


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
    response.delete_cookie("kakao_id", path='/')  # 쿠키 삭제 시 path 지정
    return response

@auth.route("/check-login", methods=["GET"])
def check_login():
    kakao_id = request.cookies.get("kakao_id")
    logger.info(f"[DEBUG] 쿠키 값: {kakao_id}")  # ✅ 쿠키 존재 여부 로깅
    
    if not kakao_id:
        logger.warning("쿠키 미존재")
        return jsonify({"loggedIn": False})
    
    user_data = redis_client_user.get(f"session:{kakao_id}")
    logger.info(f"[DEBUG] Redis 키: session:{kakao_id}, 데이터: {user_data}")  # ✅ Redis 데이터 로깅
    
    if user_data:
        return jsonify({"loggedIn": True, "userData": json.loads(user_data)})
    return jsonify({"loggedIn": False})

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