import base64

def encode_image_to_base64(image_path: str) -> str:
    """Lê uma imagem de um caminho e a codifica em base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def translate_watering_level(watering_info: dict) -> str:
    """Traduz os níveis de rega da API para texto legível."""
    level_map = {1: "seco", 2: "médio", 3: "úmido"}
    
    min_level = level_map.get(watering_info.get('min', 0), "desconhecido")
    max_level = level_map.get(watering_info.get('max', 0), "desconhecido")
    
    if min_level == max_level:
        return f"Prefere ambiente consistentemente {min_level}."
    else:
        return f"Tolera ambientes de {min_level} a {max_level}."