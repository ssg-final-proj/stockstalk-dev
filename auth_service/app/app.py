import os
import sys
from flask import Flask, render_template
from flask_login import LoginManager, login_required
from flask_migrate import Migrate
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from config import current_config, ENV
from flask_cors import CORS

# 프로젝트 루트 디렉터리를 경로에 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from db import init_app, db, User  # User 모델 추가
from .route import auth  # auth Blueprint 추가
from config import config
import logging

# .env 파일 로드
load_dotenv()

def create_app():
    app = Flask(__name__)
    config_name = os.getenv('FLASK_ENV', 'development')
    app.config.from_object(config[config_name])
    app.config['ENV'] = config_name
    CORS(app, resources={r"/*": {"origins": "*"}})

    # DB 초기화 (auth_service 스키마 사용)
    init_app(app, current_config.AUTH_SCHEMA)
    migrate = Migrate(app, db)
    
    # Flask-Login 설정
    login_manager = LoginManager()
    login_manager.init_app(app)
    app.register_blueprint(auth, url_prefix='/auth')

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.route('/')
    @login_required
    def main():
        return render_template('auth.html')

    return app

if __name__ == "__main__":
    # 로그 핸들러 설정
    handler = RotatingFileHandler('app.log', maxBytes=2000, backupCount=5)
    logging.basicConfig()
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

    app = create_app()
    app.run(host="0.0.0.0", port=8001, debug=True)
