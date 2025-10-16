import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configurações da aplicação carregadas do ambiente."""

    PLANT_ID_API_KEY = os.getenv("PLANT_ID_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    DB_USER = os.environ.get('DB_USER')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    DB_HOST = os.environ.get('DB_HOST')
    DB_PORT = os.environ.get('DB_PORT')
    DB_NAME = os.environ.get('DB_NAME')
    
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    if not PLANT_ID_API_KEY or not GEMINI_API_KEY:
        raise ValueError("As chaves de API (PLANT_ID_API_KEY, GEMINI_API_KEY) não foram encontradas no arquivo .env")