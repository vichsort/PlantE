"""
Serviço de identificação de plantas
MAIS DETALHES SOBRE A API ABAIXO:
https://www.kindwise.com/plant-id
"""

import requests

class PlantIdService:
    """
    Serviço para comunicação com a API Plant.id (Kindwise).
    Suporta identificação, avaliação de saúde e busca de detalhes da planta.
    """

    BASE_URL = "https://plant.id/api/v3/"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

    # =====================================================
    # MÉTODO BASE
    # =====================================================
    def _make_request(self, method: str, endpoint: str, data=None) -> dict:
        """Faz uma requisição genérica à API Plant.id"""
        url = f"{self.BASE_URL}{endpoint}"

        try:
            response = requests.request(method, url, headers=self.headers, json=data)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            error_text = ""
            try:
                error_text = response.text
            except Exception:
                pass

            raise Exception(
                f"{response.status_code} Client Error: {response.reason} for url: {url}\n"
                f"→ Corpo da resposta: {error_text}"
            ) from e

        except Exception as e:
            raise Exception(f"Erro inesperado na requisição: {e}")

    # =====================================================
    # IDENTIFICAÇÃO DA PLANTA
    # =====================================================
    def identify_plant(self, image_base64: str, latitude: float = None, longitude: float = None) -> dict:
        """Envia imagem para identificação da planta."""
        payload = {
            "images": [image_base64],
            "similar_images": True
        }

        if latitude is not None and longitude is not None:
            payload["latitude"] = latitude
            payload["longitude"] = longitude

        return self._make_request("POST", "identification", payload)

    # =====================================================
    # AVALIAÇÃO DE SAÚDE
    # =====================================================
    def assess_health(self, image_base64: str, latitude: float = None, longitude: float = None) -> dict:
        """Avalia a saúde da planta (detecta doenças)."""
        payload = {
            "images": [image_base64],
            "health": True
        }

        if latitude is not None and longitude is not None:
            payload["latitude"] = latitude
            payload["longitude"] = longitude

        return self._make_request("POST", "health_assessment", payload)