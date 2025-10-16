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
    # 1️⃣ IDENTIFICAÇÃO DA PLANTA
    # =====================================================
    def identify_plant(self, image_base64: str) -> dict:
        """Envia imagem para identificação da planta."""
        payload = {
            "images": [image_base64],
            "similar_images": True
        }

        return self._make_request("POST", "identification", payload)

    # =====================================================
    # 2️⃣ AVALIAÇÃO DE SAÚDE
    # =====================================================
    def assess_health(self, image_base64: str) -> dict:
        """Avalia a saúde da planta (detecta doenças)."""
        payload = {
            "images": [image_base64],
            "health": True
        }

        return self._make_request("POST", "health_assessment", payload)