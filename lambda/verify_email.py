import boto3
import os

AWS_REGION = "ap-northeast-2"
SENDER_EMAIL = os.getenv("SENDER_EMAIL")

def lambda_handler(event, context):
    if not SENDER_EMAIL:
        return {"statusCode": 400, "body": "SENDER_EMAIL 환경 변수가 필요합니다."}

    ses_client = boto3.client("ses", region_name=AWS_REGION)

    try:
        ses_client.verify_email_identity(EmailAddress=SENDER_EMAIL)
        return {"statusCode": 200, "body": f"이메일 검증 요청 전송됨: {SENDER_EMAIL}"}
    except Exception as e:
        return {"statusCode": 500, "body": f"오류 발생: {str(e)}"}