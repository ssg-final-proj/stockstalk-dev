import pymysql
import os
from urllib.parse import urlparse
from dotenv import load_dotenv  # ✅ dotenv 추가

# .env 파일 로드
load_dotenv()

# 환경 변수에서 DATABASE_URL 가져오기
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    raise ValueError("DATABASE_URL 환경 변수가 설정되지 않았습니다. Lambda 환경 변수를 확인하세요.")

# MySQL 연결 정보 파싱
def parse_database_url(url):
    parsed_url = urlparse(url)
    return {
        'host': parsed_url.hostname,
        'user': parsed_url.username,
        'password': parsed_url.password,
        'database': parsed_url.path.lstrip('/'),
        'port': parsed_url.port or 3306
    }

# 환경 변수에서 DB 정보 가져오기
db_config = parse_database_url(DATABASE_URL)

def lambda_handler(event, context):
    connection = None  # ✅ 초기값 설정

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
            # ✅ portfolio_ranking 테이블 초기화
            cursor.execute("DELETE FROM portfolio_db.portfolio_ranking")

            # ✅ 종목별 수익률을 활용한 전체 수익률 계산
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

        return {
            'statusCode': 200,
            'body': 'Ranking updated successfully!'
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': f'Error: {str(e)}'
        }

    finally:
        if connection:  # ✅ connection이 None이 아닐 때만 close() 실행
            connection.close()
