# app/__init__.py
from flask import Flask
from config import Config
from .cli import register_commands
from .extensions import db, migrate, jwt

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    
    from app.models import database

    # --- REGISTRO DOS BLUEPRINTS ---
    from .blueprints.auth_bp import auth_bp
    app.register_blueprint(auth_bp)

    register_commands(app)
    
    return app