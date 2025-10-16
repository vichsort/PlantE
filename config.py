import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configurações da aplicação carregadas do ambiente."""

    PLANT_ID_API_KEY = os.getenv("PLANT_ID_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    if not PLANT_ID_API_KEY or not GEMINI_API_KEY:
        raise ValueError("As chaves de API (PLANT_ID_API_KEY, GEMINI_API_KEY) não foram encontradas no arquivo .env")