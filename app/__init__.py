from flask import Flask
from config import Config
from .cli import register_commands
from .extensions import db, migrate, jwt
import redis

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    app.redis_client = redis.from_url(app.config['REDIS_URL'], decode_responses=True)
    
    from app.models import database
    from . import tasks

    # --- REGISTRO DOS BLUEPRINTS ---
    from .blueprints.auth_bp import auth_bp
    app.register_blueprint(auth_bp)

    from .blueprints.garden_bp import garden_bp
    app.register_blueprint(garden_bp)

    register_commands(app)
    
    return app