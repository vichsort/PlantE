"""
PRINCIPAL SISTEMA DE SEGURANÇA DO APP
o config garante que todas variáveis de ambiente componham
o sistema, assim tendo certeza que as operações, com sucesso,
possam ser repassadas para o resto do sistema. Erros aqui
crasham a aplicação e podem ser evitados garantindo
a integridade das informações inseridas dentro do seu
arquivo .env
"""

import os
from dotenv import load_dotenv
from celery.schedules import crontab

load_dotenv()

class Config:
    """Configurações da aplicação carregadas do ambiente."""

    # Chave secreta de verificação.
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')

    # Chaves de API para o funcionamento dos serviços
    #   services/gemini_service 
    #   services/plant_id_service
    PLANT_ID_API_KEY = os.getenv('PLANT_ID_API_KEY')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

    # Itens específicos do banco de dados
    # estes compõem a database_url que o psycopg2 e sqlalchemy se conectam
    DB_USER = os.environ.get('DB_USER')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    DB_HOST = os.environ.get('DB_HOST')
    DB_PORT = os.environ.get('DB_PORT')
    DB_NAME = os.environ.get('DB_NAME')

    # url completa de conexão ao db
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    # desnecessário por enquanto
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Itens específicos do redis
    # estes que compõem o redis_url que é usado pelo ec2 para conexão
    REDIS_USER = os.getenv('REDIS_USER')
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
    REDIS_ENDPOINT = os.getenv('REDIS_ENDPOINT')
    REDIS_PORT = os.getenv('REDIS_PORT')

    # url completa de conexão ao redis
    REDIS_URL = (
        f"redis://{REDIS_USER}:{REDIS_PASSWORD}@{REDIS_ENDPOINT}:{REDIS_PORT}/0"
    )

    # celery é o distribuidor de queues do sistema, que usamos
    # para as notificações quando precisamos regar ou cuidar da planta
    # o broker e o result precisam da url para sua distribuição
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    CELERY_INCLUDE = ['app.tasks']

    # schedule é justamente de quanto em quanto tempo as notificações
    # são enviadas - por que é quando verificamos elas.
    CELERYBEAT_SCHEDULE = {
        'check-watering-every-morning': {
            'task': 'tasks.check_all_plants_for_watering',
            'schedule': crontab(hour=8, minute=0), # todo dia às 8h da manhã
        },
        'check-stale-fcm-tokens-weekly': {
            'task': 'tasks.check_stale_fcm_tokens',
            'schedule': crontab(day_of_week=0, hour=3, minute=0), # todo domingo às 3
        },
        'check-user-longevity-daily': {
            'task': 'tasks.check_user_longevity',
            'schedule': crontab(hour=4, minute=0), # todo dia às 4h da manhã
        }
    }

    # quebra o app se não tiver chaves de API
    if not PLANT_ID_API_KEY or not GEMINI_API_KEY:
        raise ValueError("As chaves de API (PLANT_ID_API_KEY, GEMINI_API_KEY) não foram encontradas no arquivo .env")