from flask import Blueprint, render_template, session, redirect, request, url_for, jsonify
from datetime import datetime, timezone
from db import db, User
import requests
import os, logging
import json
import redis


# 카카오 API 설정
REST_API_KEY = os.getenv("KAKAO_SECRET_KEY")
REDIRECT_URI = "http://www.stockstalk.store/auth/kakaoLoginLogicRedirect"
STOCK_SERVICE_URL = "http://www.stockstalk.store:8002/"

# Redis 클라이언트 설정
redis_client_user = redis.StrictRedis(host=os.getenv('REDIS_HOST'), port=int(os.getenv('REDIS_PORT')), db=1, decode_responses=True)

auth = Blueprint("auth", __name__)

@auth.route("/", methods=["GET"])
def kakaologin():
    kakao_id = request.cookies.get("kakao_id")

    if kakao_id and redis_client_user.exists(f"session:{kakao_id}"):
        # Redis에서 사용자 데이터 가져오기
        user_data = json.loads(redis_client_user.get(f"session:{kakao_id}"))
        
        # 사용자 닉네임이 설정되어 있는지 확인
        if user_data.get("username") == "No username":
            return redirect(url_for('auth.set_username'))  # 닉네임 설정 페이지로 리다이렉트

        return redirect(STOCK_SERVICE_URL)  # 닉네임이 설정된 경우 stock_kr.html로 리다이렉트

    return render_template("auth.html")


@auth.route("/kakaoLoginLogic", methods=["GET"])
def kakaoLoginLogic():
    """ 카카오 로그인 URL 생성 및 리다이렉트 """
    url = (
        f"https://kauth.kakao.com/oauth/authorize?"
        f"client_id={REST_API_KEY}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
    )
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
            "client_id": REST_API_KEY,
            "redirect_uri": REDIRECT_URI,
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
            db.session.refresh(user_to_store)  # 커밋 후 세션 데이터 유지
        except Exception as e:
            db.session.rollback()
            print(f"❌ DB INSERT ERROR: {e}")
            return "DB 오류 발생", 500
    else:
        try:
            user_to_store.last_login = datetime.now(timezone.utc)
            if not user_to_store.email and email:  # ✅ 기존 유저의 이메일이 없고, 카카오에서 받은 이메일이 있으면 추가
                user_to_store.email = email
            db.session.commit()
            db.session.refresh(user_to_store)  # 커밋 후 세션 데이터 유지
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
    redis_client_user.set(f"session:{user_to_store.kakao_id}", json.dumps(user_data), ex=86400)  # 24시간 유지

    # 쿠키에 kakao_id 저장
    if user_data["username"] == "No username":
        response = redirect(url_for('auth.set_username'))  # 닉네임 설정 페이지로 리다이렉트
    else:
        response = redirect(STOCK_SERVICE_URL)  # 닉네임이 설정된 경우 stock_kr.html로 리다이렉트
    
    # response.set_cookie("kakao_id", user_to_store.kakao_id, max_age=86400)  # 24시간 동안 쿠키 유지
    response.set_cookie("kakao_id", user_to_store.kakao_id, max_age=86400, samesite="Lax", secure=False)

    print(f"✅ 쿠키 설정 완료: {user_to_store.kakao_id}")
    return response

@auth.route("/set_username", methods=["GET", "POST"])
def set_username():
    """ 사용자 닉네임 설정 """
    kakao_id = request.cookies.get("kakao_id")

    if not kakao_id:
        return redirect(url_for("auth.kakaologin"))

    # 데이터베이스에서 사용자 정보 확인
    user = User.query.filter_by(kakao_id=kakao_id).first()

    if not user:
        return redirect(url_for("auth.kakaologin"))

    # Redis에 사용자 데이터 저장 (없으면 새로 저장)
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

    if request.method == "POST":
        new_username = request.form.get("username")
        if new_username:
            user.username = new_username
            db.session.commit()

            # Redis에도 업데이트
            user_data["username"] = new_username
            redis_client_user.set(f"session:{kakao_id}", json.dumps(user_data), ex=86400)

            return redirect(STOCK_SERVICE_URL)

    return render_template("set_username.html", user=user_data)

@auth.route("/check_nickname", methods=["GET"])
def check_nickname():
    """ 닉네임 중복 체크 API """
    username = request.args.get("username", "").strip()
    if not username:
        return jsonify({"exists": False})

    existing_user = User.query.filter_by(username=username).first()
    return jsonify({"exists": bool(existing_user)})

@auth.route("/logout", methods=["GET"])
def logout():
    """ 로그아웃 (Redis 세션 삭제) """
    kakao_id = request.cookies.get("kakao_id")

    if kakao_id and redis_client_user.exists(f"session:{kakao_id}"):
        redis_client_user.delete(f"session:{kakao_id}")  # Redis에서 세션 삭제

    response = redirect(STOCK_SERVICE_URL)
    response.delete_cookie("kakao_id")  # 쿠키에서 kakao_id 삭제
    return response

@auth.route("/check-login", methods=["GET"])
def check_login():
    """ 로그인 상태 확인 API """
    kakao_id = request.cookies.get("kakao_id")

    if kakao_id and redis_client_user.exists(f"session:{kakao_id}"):
        user_data = json.loads(redis_client_user.get(f"session:{kakao_id}"))
        return jsonify({"loggedIn": True, "kakao_id": user_data["kakao_id"]})

    return jsonify({"loggedIn": False})

@auth.route('/api/update_user', methods=['POST'])
def update_user():
    """사용자 정보 업데이트"""
    try:
        data = request.json
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
        user.seed_usd = seed_usd
        db.session.commit()

        # Redis 업데이트
        user_data = redis_client_user.get(f'session:{kakao_id}')
        if user_data:
            user_data = json.loads(user_data)
            user_data['seed_krw'] = seed_krw
            user_data['seed_usd'] = seed_usd
            redis_client_user.set(f'session:{kakao_id}', json.dumps(user_data), ex=86400)
        return jsonify({"message": "User updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
