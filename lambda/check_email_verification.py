import boto3
import pymysql
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# AWS SES 클라이언트 생성
ses_client = boto3.client('ses', region_name='ap-northeast-2')

# MySQL 연결 정보 파싱
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    raise ValueError("DATABASE_URL 환경 변수가 설정되지 않았습니다. Lambda 환경 변수를 확인하세요.")

def parse_database_url(url):
    parsed_url = urlparse(url)
    return {
        'host': parsed_url.hostname,
        'user': parsed_url.username,
        'password': parsed_url.password,
        'database': parsed_url.path.lstrip('/'),
        'port': parsed_url.port or 3306
    }

db_config = parse_database_url(DATABASE_URL)

def lambda_handler(event, context):
    connection = None
    try:
        # MySQL 연결
        connection = pymysql.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database'],
            port=db_config['port'],
            cursorclass=pymysql.cursors.DictCursor
        )

        with connection.cursor() as cursor:
            # ✅ 이메일 검증이 필요한 사용자 조회
            cursor.execute("SELECT kakao_id, email FROM auth_db.users WHERE email IS NOT NULL AND email_verified = FALSE")
            users = cursor.fetchall()

            verified_users = []
            for user in users:
                email = user['email']
                kakao_id = user['kakao_id']

                response = ses_client.get_identity_verification_attributes(
                    Identities=[email]
                )

                verification_status = response['VerificationAttributes'].get(email, {}).get('VerificationStatus', 'Not Found')

                if verification_status == "Success":
                    verified_users.append((email, kakao_id))

            # ✅ DB에 검증된 이메일 반영
            if verified_users:
                for email, kakao_id in verified_users:
                    cursor.execute(
                        "UPDATE auth_db.users SET email_verified = TRUE WHERE kakao_id = %s",
                        (kakao_id,)
                    )
                connection.commit()

        return {'statusCode': 200, 'body': f"✅ 검증된 이메일 업데이트 완료: {len(verified_users)}개"}

    except Exception as e:
        return {'statusCode': 500, 'body': f'❌ 오류 발생: {str(e)}'}

    finally:
        if connection:
            connection.close()