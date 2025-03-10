import mojito

class CustomKoreaInvestment(mojito.KoreaInvestment):
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

# 기존 Mojito2의 다른 메서드들도 필요에 따라 오버라이드할 수 있습니다.