from flask import Flask
from config import Config
from .cli import register_commands
from .extensions import db, migrate

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    from app.models import database

    register_commands(app)

    return app