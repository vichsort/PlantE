from pydantic import BaseModel, Field
from typing import List

# SUB SCHEMAS -
class OriginInfo(BaseModel):
    """Esquema para a origem da planta."""
    country: str = Field(..., description="País de origem da planta.")
    region: str = Field(..., description="Região específica dentro do país de origem.")
    habitat: str = Field(..., description="Tipo de habitat onde a planta é encontrada.")

class TaxonomyInfo(BaseModel):
    """Esquema para a taxonomia da planta."""
    classe: str = Field(..., description="Classe taxonômica da planta.")
    genus: str = Field(..., description="Gênero taxonômico da planta.")
    ordem: str = Field(..., description="Ordem taxonômica da planta.")
    familia: str = Field(..., description="Família taxonômica da planta.")
    filo: str = Field(..., description="Filo taxonômico da planta.")

class FoodRecipe(BaseModel):
    """Esquema para uma receita usando a planta."""
    name: str = Field(..., description="Nome da receita.")
    ingredients: List[str] = Field(..., description="Lista de ingredientes para a receita.")

class MedicinalUse(BaseModel):
    """Esquema para o uso medicinal da planta."""
    how_to_use: str = Field(..., description="Como utilizar a planta para fins medicinais.")
    benefits: List[str] = Field(..., description="Lista de benefícios medicinais.")

# MAIN SCHEMAS -
class PlantInfo(BaseModel):
    """Esquema para informações profundas da planta gerada pelo Gemini."""
    popular_name: List[str] = Field(..., description="Uma lista dos principais nomes da planta.")
    description: str = Field(..., description="Uma breve descrição da planta.")
    taxonomy: TaxonomyInfo = Field(..., description="A classificação taxonômica completa da planta.")
    is_edible: bool = Field(..., description="A planta é comestível? True ou False.")
    water: str = Field(..., description="Quantas vezes por semana a planta deve ser regada.")
    season: str = Field(..., description="Qual a melhor estação do ano para plantar essa planta.")
    sunlight: str = Field(..., description="Qual o nível de luz solar que a planta necessita.")
    soil: str = Field(..., description="Qual o tipo de solo ideal para essa planta crescer.")
    origin: OriginInfo = Field(..., description="Informações sobre a origem da planta.")

class DiseaseInfo(BaseModel):
    """Esquema para informações de doenças geradas pelo Gemini."""
    disease_name: str = Field(..., description="O nome comum da doença.")
    symptoms: List[str] = Field(..., description="Uma lista dos principais sintomas da doença.")
    treatment_plan: List[str] = Field(..., description="Passos para tratar a doença.")
    recovery_time: str = Field(..., description="Tempo estimado para a recuperação da planta.")

class NutritionalInfo(BaseModel):
    """Esquema para informações sobre alimentos / bebidas que uma planta oferece gerada pelo Gemini."""
    tea: List[str] = Field(..., description="Pode-se fazer chá para consumo? Se for, responda essa questão com: como e quais benefícios.")
    food: FoodRecipe = Field(..., description="Uma receita que pode ser feita com a planta.")
    heal: MedicinalUse = Field(..., description="Informações sobre o uso medicinal da planta.")
    seasoning: str = Field(..., description="Se essa planta for usada como tempero, responda essa questão com: em que pratos se usa esse tempero.")
