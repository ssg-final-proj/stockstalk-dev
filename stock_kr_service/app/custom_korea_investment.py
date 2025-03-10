import requests
from mojito.koreainvestment import KoreaInvestment

class CustomKoreaInvestment(KoreaInvestment):
    def __init__(self, api_key, api_secret, acc_no):
        super().__init__(api_key=api_key, api_secret=api_secret, acc_no=acc_no)

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
        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
            raise Exception(f"Failed to issue access token: {response.status_code}, {response.text}")
        return response.json()
