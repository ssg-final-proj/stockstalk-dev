# auth.py
import os
from .custom_korea_investment import CustomKoreaInvestment

def create_broker():
    key_path = os.getenv("KOREA_INVESTMENT_KEY_PATH")
    if not key_path:
        raise ValueError("KOREA_INVESTMENT_KEY_PATH 환경 변수가 설정되지 않았습니다.")

    with open(key_path) as f:
        lines = f.readlines()
        key = lines[0].strip()
        secret = lines[1].strip()
        acc_no = lines[2].strip()

    return CustomKoreaInvestment(
        api_key=key,
        api_secret=secret,
        acc_no=acc_no
    )
