import base64

def encode_image_to_base64(image_path: str) -> str:
    """Lê uma imagem de um caminho e a codifica em base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')
