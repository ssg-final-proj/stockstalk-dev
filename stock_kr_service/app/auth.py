import os
import mojito
import redis
import time
from datetime import timedelta

def create_broker():
    key_path = os.getenv("KOREA_INVESTMENT_KEY_PATH")
    redis_host = os.getenv("REDIS_HOST", "redis.infra.svc.cluster.local")
    redis_port = int(os.getenv("REDIS_PORT", 6379))

    if not key_path:
        raise ValueError("KOREA_INVESTMENT_KEY_PATH 환경 변수가 설정되지 않았습니다.")

    redis_client = redis.StrictRedis(
        host=redis_host,
        port=redis_port,
        db=4,
        decode_responses=True
    )

    with open(key_path) as f:
        lines = f.readlines()
        key = lines[0].strip()
        secret = lines[1].strip()
        acc_no = lines[2].strip()

    try:
        # Redis에서 기존 토큰 확인
        token = redis_client.get("koreainvestment:access_token")
        if token:
            broker = mojito.KoreaInvestment(
                api_key=key,
                api_secret=secret,
                acc_no=acc_no
            )
            broker.access_token = token  # Redis에서 가져온 토큰 사용
            print("✅ Redis에서 캐시된 토큰 사용")
            return broker

        # Redis에 토큰이 없으면 새로 발급
        print("⚠️ Redis에 토큰이 없어 새로 발급합니다.")
        broker = mojito.KoreaInvestment(
            api_key=key,
            api_secret=secret,
            acc_no=acc_no
        )

        if not broker.access_token:
            raise ValueError("토큰 발급 실패: API 응답에 access_token 없음")

        # 새로 발급한 토큰 Redis에 저장 (24시간 유효)
        redis_client.setex(
            "koreainvestment:access_token",
            timedelta(hours=24),
            broker.access_token
        )
        print("✅ 새 토큰 발급 및 Redis 저장 완료 (24시간 유효)")
        return broker

    except redis.exceptions.ConnectionError as e:
        print(f"⚠️ Redis 연결 실패: {e}, 새 토큰 발급")
        return mojito.KoreaInvestment(
            api_key=key,
            api_secret=secret,
            acc_no=acc_no
        )
    except Exception as e:
        print(f"❌ 예외 발생: {e}")
        raise

