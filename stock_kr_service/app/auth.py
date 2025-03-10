import os
import mojito

def create_broker():
    key_path = os.getenv("KOREA_INVESTMENT_KEY_PATH")
    if not key_path:
        raise ValueError("KOREA_INVESTMENT_KEY_PATH 환경 변수가 설정되지 않았습니다.")

    # 인증 정보를 파일에서 읽어옵니다.
    with open(key_path) as f:
        lines = f.readlines()
        key = lines[0].strip().split('=')[1]
        secret = lines[1].strip().split('=')[1]
        acc_no = lines[2].strip().split('=')[1]

    return mojito.KoreaInvestment(
        app_key=key,  # api_key에서 app_key로 변경
        app_secret=secret,  # api_secret에서 app_secret으로 변경
        acc_no=acc_no
    )
