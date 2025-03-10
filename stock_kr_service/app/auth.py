import os
import mojito
import redis
from datetime import timedelta

def create_broker():
    # 환경 변수에서 키 경로 및 Redis 설정 읽기
    key_path = os.getenv("KOREA_INVESTMENT_KEY_PATH")
    redis_host = os.getenv("REDIS_HOST", "redis.infra.svc.cluster.local")  # ✅ 기본값 설정
    redis_port = int(os.getenv("REDIS_PORT", 6379))  # ✅ 포트 기본값 6379

    if not key_path:
        raise ValueError("KOREA_INVESTMENT_KEY_PATH 환경 변수가 설정되지 않았습니다.")

    # Redis 클라이언트 초기화 (db4 사용)
    redis_client = redis.StrictRedis(
        host=redis_host,
        port=redis_port,
        db=4,  # ✅ db4 지정
        decode_responses=True
    )

    # 키 파일 읽기
    with open(key_path) as f:
        lines = f.readlines()
        key = lines[0].strip()
        secret = lines[1].strip()
        acc_no = lines[2].strip()

    try:
        # Redis에서 토큰 조회
        token = redis_client.get("koreainvestment:access_token")
        
        if token:
            # 캐시된 토큰 사용
            broker = mojito.KoreaInvestment(
                api_key=key,
                api_secret=secret,
                acc_no=acc_no
            )
            broker.access_token = token  # ✅ 토큰 강제 주입
            print("✅ Redis에서 캐시된 토큰 사용")
            return broker

        # 토큰 없으면 새로 발급
        broker = mojito.KoreaInvestment(
            api_key=key,
            api_secret=secret,
            acc_no=acc_no
        )
        
        # 새 토큰 Redis에 저장 (23시간 유효)
        redis_client.setex(
            "koreainvestment:access_token",
            timedelta(hours=23),  # ✅ 24시간 유효 토큰에 1시간 마진
            broker.access_token
        )
        print("✅ 새 토큰 발급 및 Redis 저장 완료")
        return broker

    except redis.exceptions.ConnectionError as e:
        # Redis 연결 실패 시 예외 처리
        print(f"⚠️ Redis 연결 실패: {e}, 새 토큰 발급")
        return mojito.KoreaInvestment(
            api_key=key,
            api_secret=secret,
            acc_no=acc_no
        )
