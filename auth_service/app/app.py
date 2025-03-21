import os
import sys
from flask import Flask, render_template, jsonify, url_for
from flask_login import LoginManager
from flask_migrate import Migrate
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from config import current_config
from flask_cors import CORS
from sqlalchemy import text

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from db import init_app, db, User
from .route import auth
from config import config
import logging

load_dotenv()

def create_app():
    app = Flask(__name__)
    config_name = os.getenv('FLASK_ENV', 'development')
    app.config.from_object(config[config_name])
    
    CORS(app, 
    resources={r"/*": {
        "origins": ["https://www.stockstalk.store"],
        "supports_credentials": True,
        "expose_headers": ["Set-Cookie"]  # 쿠키 헤더 노출
    }})

    db.init_app(app)

    with app.app_context():
        init_app(app, current_config.AUTH_SCHEMA)
        db.create_all()

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    app.register_blueprint(auth, url_prefix='/auth')

    @app.route('/healthz', methods=['GET'])
    def health_check():
        return jsonify({"status": "ok"}), 200

    @app.route('/readiness', methods=['GET'])
    def readiness_check():
        try:
            with db.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return jsonify({"status": "ready"}), 200
        except Exception as e:
            return jsonify({"status": "not ready", "error": str(e)}), 500
    @app.context_processor
    def override_url_for():
        return dict(url_for=dated_url_for)

    def dated_url_for(endpoint, **values):
        if endpoint == 'static':
            filename = values.get('filename', None)
            if filename:
                file_path = os.path.join(app.root_path, endpoint, filename)
                values['v'] = int(os.stat(file_path).st_mtime)
        return url_for(endpoint, **values)
    
    return app

if __name__ == "__main__":
    handler = RotatingFileHandler('app.log', maxBytes=2000, backupCount=5)
    logging.basicConfig()
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    app = create_app()
    migrate = Migrate(app, db)
    app.config['DEBUG'] = True
    app.config['TEMPLATES_AUTO_RELOAD'] 
    app.run(host="0.0.0.0", port=8001)