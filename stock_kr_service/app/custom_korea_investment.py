import time
import requests
from mojito.koreainvestment import KoreaInvestment

class CustomKoreaInvestment(KoreaInvestment):
    def __init__(self, api_key, api_secret, acc_no):
        super().__init__(api_key=api_key, api_secret=api_secret, acc_no=acc_no)
        self.access_token = None
        self.token_expired_at = None

    def issue_access_token(self):
        # 이미 발급된 토큰이 유효하면 재사용
        if self.access_token and self.token_expired_at and time.time() < self.token_expired_at:
            return self.access_token

        # 새 토큰 발급 요청
        path = "oauth2/tokenP"
        url = f"{self.base_url}/{path}"
        headers = {
            "content-type": "application/json",
            "appkey": self.api_key,
            "appsecret": self.api_secret
        }
        data = {
            "grant_type": "client_credentials",
            "appkey": self.api_key,
            "appsecret": self.api_secret
        }
        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
            raise Exception(f"Failed to issue access token: {response.status_code}, {response.text}")

        # 응답에서 토큰과 만료 시간 저장
        resp_data = response.json()
        self.access_token = f"Bearer {resp_data['access_token']}"
        expires_in = int(resp_data.get("expires_in", 86400))  # 기본 만료 시간: 24시간
        self.token_expired_at = time.time() + expires_in - 60  # 만료 시간 60초 전까지 유효
        return self.access_token
