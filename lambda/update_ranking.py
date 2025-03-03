import pymysql
import boto3
import os
from urllib.parse import urlparse

AWS_REGION = "ap-northeast-2"
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL or not SENDER_EMAIL:
    raise ValueError("필요한 환경 변수가 설정되지 않았습니다.")

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

def send_email(recipient_email, kakao_id, profit_rate_total, p_rank):
    subject = "가상 주식 거래 시스템 - 순위 업데이트"
    body = f"""
    안녕하세요, {kakao_id}님!

    최근 순위가 업데이트되었습니다.
    
    📈 총 수익률: {profit_rate_total:.2f}%
    🏆 현재 순위: {p_rank}위

    계속해서 좋은 성과 내시길 바랍니다!
    """

    ses_client.send_email(
        Source=SENDER_EMAIL,
        Destination={"ToAddresses": [recipient_email]},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Text": {"Data": body}}
        }
    )

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
            cursor.execute("DELETE FROM portfolio_db.portfolio_ranking")

            query = """
            INSERT INTO portfolio_db.portfolio_ranking (kakao_id, profit_rate_total, p_rank)
            SELECT kakao_id,
                   (SUM(initial_investment * profit_rate) / NULLIF(SUM(initial_investment), 0)) AS profit_rate_total,
                   RANK() OVER (ORDER BY (SUM(initial_investment * profit_rate) / NULLIF(SUM(initial_investment), 0)) DESC) AS p_rank
            FROM portfolio_db.portfolios
            WHERE initial_investment > 0
            GROUP BY kakao_id;
            """
            cursor.execute(query)
            connection.commit()

            cursor.execute("""
            SELECT u.kakao_id, u.email, r.profit_rate_total, r.p_rank
            FROM auth_db.users u
            JOIN portfolio_db.portfolio_ranking r ON u.kakao_id = r.kakao_id
            WHERE u.email IS NOT NULL
            """)
            
            users = cursor.fetchall()

            for user in users:
                send_email(user["email"], user["kakao_id"], user["profit_rate_total"], user["p_rank"])

        return {"statusCode": 200, "body": "순위 업데이트 및 이메일 전송 완료"}

    except Exception as e:
        return {"statusCode": 500, "body": f"오류 발생: {str(e)}"}

    finally:
        if connection:
            connection.close()