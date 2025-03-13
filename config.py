import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_TYPE = 'filesystem'
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 5,
        "max_overflow": 3,
        "pool_recycle": 1800,
        "pool_pre_ping": True
    }
    REDIS_HOST = os.getenv('REDIS_HOST', 'redis.infra.svc.cluster.local')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    CACHE_DURATION = int(os.getenv('CACHE_DURATION', 100))
    KAFKA_BROKER_HOST = os.getenv('KAFKA_BROKER_HOST', 'kafka:9092')

    base_dir = os.path.abspath(os.path.dirname(__file__))
    project_root = os.path.abspath(os.path.join(base_dir, '..'))

    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')

    AUTH_SCHEMA = os.getenv('AUTH_SCHEMA', 'auth_db')
    EXCHANGE_SCHEMA = os.getenv('EXCHANGE_SCHEMA', 'exchange_db')
    PORTFOLIO_SCHEMA = os.getenv('PORTFOLIO_SCHEMA', 'portfolio_db')

    KOREA_INVESTMENT_KEY_PATH = os.path.join(project_root, os.getenv('KOREA_INVESTMENT_KEY_PATH', ''))

    SQLALCHEMY_BINDS = {
        'auth': SQLALCHEMY_DATABASE_URI + '/' + AUTH_SCHEMA,
        'portfolio': SQLALCHEMY_DATABASE_URI + '/' + PORTFOLIO_SCHEMA,
        'exchange': SQLALCHEMY_DATABASE_URI + '/' + EXCHANGE_SCHEMA,
        'orders': SQLALCHEMY_DATABASE_URI + '/' + PORTFOLIO_SCHEMA,
        'stock' : SQLALCHEMY_DATABASE_URI + '/' + PORTFOLIO_SCHEMA,
    }

    BASE_URL = os.getenv('URL', 'https://www.stockstalk.store')
    AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "https://www.stockstalk.store/auth")
    EXCHANGE_SERVICE_URL = os.getenv("EXCHANGE_SERVICE_URL", "https://www.stockstalk.store/exchange")
    PORTFOLIO_SERVICE_URL = os.getenv("PORTFOLIO_SERVICE_URL", "https://www.stockstalk.store/portfolio")
    REST_API_KEY = os.getenv('KAKAO_SECRET_KEY')
    
    SESSION_COOKIE_SECURE = True
    COOKIE_DOMAIN = os.getenv('COOKIE_DOMAIN', '.stockstalk.store')
    SECURE_COOKIES = os.getenv('SECURE_COOKIES', 'True').lower() == 'true'

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True
    COOKIE_DOMAIN = 'localhost'
    SECURE_COOKIES = False

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

ENV = os.getenv('FLASK_ENV', 'default')
current_config = config[ENV]
