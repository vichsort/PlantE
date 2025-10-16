from google import genai
from ..models.schemas import PlantInfo, DiseaseInfo, NutritionalInfo

class GeminiService:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def get_details_about_plant(self, plant_name: str) -> PlantInfo:
        """
        Gera detalhes sobre uma planta usando o Gemini.
        """
        prompt = (
            f"Minha planta, de nome científico '{plant_name} está saudável. "
            "Eu preciso das seguintes informações em português do Brasil: "
            "1. Uma lista de nomes populares. "
            "2. Uma breve descrição da planta. "
            "3. A taxonomia (classe, gênero, ordem, família, filo). "
            "4. Se é comestível (true/false). "
            "5. Frequência de rega por semana. "
            "6. Melhor estação para o plantio. "
            "7. Nível de luz solar necessário. "
            "8. Tipo de solo ideal."
            "9. Informações sobre a origem (país, região, habitat)."
        )

        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": PlantInfo,
            },
        )
        
        return PlantInfo.model_validate_json(response.text)

    def get_disease_treatment_plan(self, plant_name: str, disease_name: str) -> DiseaseInfo:
        """
        Gera um plano de tratamento para uma doença de planta usando o Gemini.
        """
        prompt = (
            f"Minha planta, de nome científico '{plant_name}', foi diagnosticada com a doença '{disease_name}'. "
            "Por favor, forneça as seguintes informações em português do Brasil:\n"
            "1. Os principais sintomas visíveis dessa doença.\n"
            "2. Um plano de tratamento claro e prático.\n"
            "3. Uma estimativa de tempo para a recuperação da planta."
        )

        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": DiseaseInfo,
            },
        )
        
        return DiseaseInfo.model_validate_json(response.text)
    
    def get_nutritional_details(self, plant_name: str) -> PlantInfo:
        """
        Gera detalhes alimentícios sobre uma planta usando o Gemini.
        """
        prompt = (
            f"Minha planta, de nome científico '{plant_name} está saudável. "
            "Eu preciso das seguintes informações em português do Brasil: "
            "1. É possível fazer chá? Se sim, como fazer e quais os benefícios. "
            "2. Uma receita (nome e ingredientes) de um alimento que pode ser feito com a planta. "
            "3. Usos medicinais: se houver, explique como usar e os benefícios. "
            "4. Se for usada como tempero, em que tipos de pratos combina."
        )

        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": NutritionalInfo,
            },
        )
        
        return NutritionalInfo.model_validate_json(response.text)