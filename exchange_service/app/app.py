import os
import sys
import logging
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from flask_migrate import Migrate
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from config import current_config
from flask_cors import CORS

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

load_dotenv()

from db import init_app, db
from config import config
from route import exchange

def create_app():
    app = Flask(__name__)
    config_name = os.getenv('FLASK_ENV', 'development')
    app.config.from_object(config[config_name])
    
    CORS(app, resources={r"/*": {"origins": "*"}})
    db.init_app(app)

    with app.app_context():
        init_app(app, current_config.EXCHANGE_SCHEMA)
        db.create_all()

    app.register_blueprint(exchange, url_prefix='/exchange')
    
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
        
    return app



if __name__ == "__main__":
    handler = RotatingFileHandler('app.log', maxBytes=2000, backupCount=5)
    logging.basicConfig()
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

    app = create_app()
    app.run(host="0.0.0.0", port=8004, debug=True)
