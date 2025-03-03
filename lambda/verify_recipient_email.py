import pymysql
import boto3
import os
from urllib.parse import urlparse

AWS_REGION = "ap-northeast-2"
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL 환경 변수가 설정되지 않았습니다.")

def parse_database_url(url):
    parsed_url = urlparse(url)
    return {
        "host": parsed_url.hostname,
        "user": parsed_url.username,
        "password": parsed_url.password,
        "database": parsed_url.path.lstrip("/"),
        "port": parsed_url.port or 3306
    }

db_config = parse_database_url(DATABASE_URL)
ses_client = boto3.client("ses", region_name=AWS_REGION)

def lambda_handler(event, context):
    connection = None

    try:
        connection = pymysql.connect(
            host=db_config["host"],
            user=db_config["user"],
            password=db_config["password"],
            database=db_config["database"],
            port=db_config["port"],
            cursorclass=pymysql.cursors.DictCursor
        )

        with connection.cursor() as cursor:
            cursor.execute("SELECT email FROM auth_db.users WHERE email_verified = FALSE AND email IS NOT NULL")
            users = cursor.fetchall()

            for user in users:
                ses_client.verify_email_identity(EmailAddress=user["email"])
                print(f"이메일 검증 요청 전송됨: {user['email']}")

        return {"statusCode": 200, "body": "사용자 이메일 검증 요청 완료"}

    except Exception as e:
        return {"statusCode": 500, "body": f"오류 발생: {str(e)}"}

    finally:
        if connection:
            connection.close()