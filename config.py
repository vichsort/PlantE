import os
from dotenv import load_dotenv
from celery.schedules import crontab

load_dotenv()

class Config:
    """Configurações da aplicação carregadas do ambiente."""

    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')

    PLANT_ID_API_KEY = os.getenv('PLANT_ID_API_KEY')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

    DB_USER = os.environ.get('DB_USER')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    DB_HOST = os.environ.get('DB_HOST')
    DB_PORT = os.environ.get('DB_PORT')
    DB_NAME = os.environ.get('DB_NAME')

    REDIS_USER = os.getenv('REDIS_USER')
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
    REDIS_ENDPOINT = os.getenv('REDIS_ENDPOINT')
    REDIS_PORT = os.getenv('REDIS_PORT')

    REDIS_URL = (
        f"redis://{REDIS_USER}:{REDIS_PASSWORD}@{REDIS_ENDPOINT}:{REDIS_PORT}/0"
    )
    
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL

    CELERYBEAT_SCHEDULE = {
        'check-watering-every-morning': {
            # O 'name' da tarefa que vamos criar em 'tasks.py'
            'task': 'tasks.check_all_plants_for_watering',
            # 'schedule': crontab(minute='*/1') # <<< Para testar: roda a cada 1 minuto
            'schedule': crontab(hour=8, minute=0), # Para produção: todo dia às 8h da manhã
        },
    }

    if not PLANT_ID_API_KEY or not GEMINI_API_KEY:
        raise ValueError("As chaves de API (PLANT_ID_API_KEY, GEMINI_API_KEY) não foram encontradas no arquivo .env")