import pymysql
import boto3
import os
from urllib.parse import urlparse

# AWS 설정
AWS_REGION = "ap-northeast-2"
SENDER_EMAIL = os.getenv("SENDER_EMAIL")  # 발신자 이메일
DATABASE_URL = os.getenv("DATABASE_URL")  # RDS 연결 URL

if not DATABASE_URL or not SENDER_EMAIL:
    raise ValueError("필요한 환경 변수가 설정되지 않았습니다.")

# 데이터베이스 URL 파싱
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

# ✅ AWS SES에서 검증된 이메일만 발송 가능
VERIFIED_RECIPIENTS = ["redcedar1@naver.com"]  # SES에서 검증된 이메일 목록

# 이메일 전송 함수
def send_email(recipient_email, username, profit_rate_total, p_rank):
    if recipient_email not in VERIFIED_RECIPIENTS:
        print(f"🚨 {recipient_email}은(는) 검증되지 않은 이메일입니다. 이메일 전송 건너뜀.")
        return  # 검증되지 않은 이메일이면 전송하지 않음

    subject = "가상 주식 거래 시스템 - 순위 업데이트"
    body = f"""
    안녕하세요, {username}님!

    최근 순위가 업데이트되었습니다.
    
    📈 총 수익률: {profit_rate_total:.2f}%
    🏆 현재 순위: {p_rank}위

    계속해서 좋은 성과 내시길 바랍니다!
    """

    print(f"📧 이메일 전송 준비: {recipient_email}")  # 디버깅 로그
    ses_client.send_email(
        Source=SENDER_EMAIL,
        Destination={"ToAddresses": [recipient_email]},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Text": {"Data": body}}
        }
    )
    print(f"✅ 이메일 전송 완료: {recipient_email}")  # 디버깅 로그

# Lambda 핸들러
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
            # 기존 순위 삭제
            cursor.execute("DELETE FROM portfolio_db.portfolio_ranking")

            # 전체 수익률 계산 및 순위 업데이트
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

            # ✅ 이메일 전송 대상 조회 (`username` 추가)
            cursor.execute("""
            SELECT u.kakao_id, u.username, u.email, r.profit_rate_total, r.p_rank
            FROM auth_db.users u
            JOIN portfolio_db.portfolio_ranking r ON u.kakao_id = r.kakao_id
            WHERE u.email IS NOT NULL;
            """)
            
            users = cursor.fetchall()
            print(f"✅ 조회된 사용자 수: {len(users)}명")  # 디버깅 로그

            for user in users:
                username = user["username"]  # ✅ `kakao_id` 대신 `username` 사용
                new_rank = user["p_rank"]
                
                print(f"📧 이메일 전송 준비: {user['email']} (순위: {new_rank})")  # 디버깅 로그
                send_email(user["email"], username, user["profit_rate_total"], new_rank)
                print(f"✅ 이메일 전송 완료: {user['email']}")  # 디버깅 로그

        return {"statusCode": 200, "body": "순위 업데이트 및 이메일 전송 완료"}

    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")  # 디버깅 로그
        return {"statusCode": 500, "body": f"오류 발생: {str(e)}"}

    finally:
        if connection:
            connection.close()
            print("✅ 데이터베이스 연결 종료")  # 디버깅 로그