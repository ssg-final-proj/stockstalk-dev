import mojito

class CustomKoreaInvestment(mojito.KoreaInvestment):
    def __init__(self, api_key, api_secret, acc_no):
        # Mojito의 __init__ 메서드 호출
        super().__init__(api_key=api_key, api_secret=api_secret, acc_no=acc_no)
        # 필요한 추가 초기화 코드 작성

    def issue_access_token(self):
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
        return self._send_request("POST", url, headers=headers, data=data)
