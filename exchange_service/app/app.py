import os
import sys
import logging
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from config import current_config, ENV
from flask_cors import CORS

# 프로젝트 루트 디렉터리를 경로에 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# .env 파일 로드
load_dotenv()

# 모듈 임포트
from db import init_app, db
from config import config  # config 모듈 가져오기
from route import exchange  # 기존 auth 대신 exchange 블루프린트 등록

def create_app():
    """ Flask 애플리케이션 생성 및 설정 """
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}})
    
    # ✅ 환경 설정
    env = os.getenv('FLASK_ENV', 'default')
    app.config.from_object(config[env])
    app.config['SQLALCHEMY_DATABASE_URI'] = config[env].SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['ENV'] = env  # Flask 환경 설정

    # ✅ DB 초기화
    init_app(app, current_config.EXCHANGE_SCHEMA)
    migrate = Migrate(app, db)

    # ✅ 블루프린트 등록 (exchange 블루프린트 추가)
    app.register_blueprint(exchange)

    # ✅ 기본 라우트: exchange.html 렌더링
    @app.route('/')
    def main():
        return render_template('exchange.html', exchange_rate=1450.00, message="")

    return app

if __name__ == "__main__":
    # ✅ 로그 설정
    handler = RotatingFileHandler('app.log', maxBytes=2000, backupCount=5)
    logging.basicConfig()
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

    # ✅ Flask 앱 실행 (포트 8004로 변경)
    app = create_app()
    app.run(host="0.0.0.0", port=8004, debug=True)
