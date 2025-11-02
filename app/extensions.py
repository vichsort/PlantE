"""
Construtor do sistema de segurança
Em outras palavras, o que salva o sqlalchemy
e jwt de começar no mesmo ponto de partida
e fazer importação circular.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
redis_client = None