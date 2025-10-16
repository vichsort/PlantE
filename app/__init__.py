from flask import Flask
from config import Config
from .cli import register_commands

def create_app(config_class=Config):
    """
    Factory para criar e configurar a instância da aplicação Flask.
    """
    app = Flask(__name__)
    
    # 1. Carrega a configuração a partir do objeto importado
    app.config.from_object(config_class)
    
    # 2. Registra os comandos CLI
    register_commands(app)

    return app