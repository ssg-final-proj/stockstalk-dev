import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_TYPE = 'filesystem'
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 280,
    }
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    CACHE_DURATION = int(os.getenv('CACHE_DURATION', 300))
    KAFKA_BROKER_HOST = os.getenv('KAFKA_BROKER_HOST', 'localhost:9092')
    
    base_dir = os.path.abspath(os.path.dirname(__file__))
    project_root = os.path.abspath(os.path.join(base_dir, '..'))
    
    DB_NAME = os.environ.get('DB_NAME')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    
    # 스키마 설정 추가
    AUTH_SCHEMA = os.getenv('AUTH_SCHEMA', 'auth_db')
    EXCHANGE_SCHEMA = os.getenv('EXCHANGE_SCHEMA', 'exchange_db')
    PORTFOLIO_SCHEMA = os.getenv('PORTFOLIO_SCHEMA', 'portfolio_db')
    STOCK_SCHEMA = os.getenv('STOCK_SCHEMA', 'stock_db') # STOCK_SCHEMA 추가

    KOREA_INVESTMENT_KEY_PATH = os.path.join(project_root, os.getenv('KOREA_INVESTMENT_KEY_PATH', ''))

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True

class ProductionConfig(Config):
    DEBUG = False

class AuthServiceConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'auth_service': AuthServiceConfig,
    'default': DevelopmentConfig
}

# 현재 환경 설정
ENV = os.getenv('FLASK_ENV', 'default')
current_config = config[ENV]
