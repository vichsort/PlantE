"""
Utilitário para fornecer coordenadas geográficas de fallback.

Este módulo contém um dicionário de coordenadas (latitude e longitude)
para todas as capitais dos estados brasileiros e do Distrito Federal.
É usado para fornecer uma localização de fallback para a API do Plant.id
quando o usuário nega a permissão de localização no app.
"""

# Coordenadas do fallback final (Brasília, DF)
DEFAULT_FALLBACK_COORDINATES = {
    'lat': -15.779722,
    'lon': -47.929722
}

# Dicionário de coordenadas de fallback por estado (baseado nas capitais)
# Chaves devem ser os nomes completos dos estados (em title case)
_STATE_FALLBACK_COORDINATES = {
    # --- Região Norte ---
    'Acre': {'lat': -9.97499, 'lon': -67.8243},         # Rio Branco
    'Amapá': {'lat': 0.03889, 'lon': -51.06639},        # Macapá
    'Amazonas': {'lat': -3.119028, 'lon': -60.021731},  # Manaus
    'Pará': {'lat': -1.455028, 'lon': -48.5025},        # Belém
    'Rondônia': {'lat': -8.76194, 'lon': -63.90389},    # Porto Velho
    'Roraima': {'lat': 2.82384, 'lon': -60.6753},       # Boa Vista
    'Tocantins': {'lat': -10.2128, 'lon': -48.3603},    # Palmas
    
    # --- Região Nordeste ---
    'Alagoas': {'lat': -9.66583, 'lon': -35.73528},     # Maceió
    'Bahia': {'lat': -12.97194, 'lon': -38.50167},     # Salvador
    'Ceará': {'lat': -3.73194, 'lon': -38.52667},      # Fortaleza
    'Maranhão': {'lat': -2.53073, 'lon': -44.3068},    # São Luís
    'Paraíba': {'lat': -7.11948, 'lon': -34.84501},    # João Pessoa
    'Pernambuco': {'lat': -8.05783, 'lon': -34.88289}, # Recife
    'Piauí': {'lat': -5.09097, 'lon': -42.8038},       # Teresina
    'Rio Grande do Norte': {'lat': -5.79444, 'lon': -35.20889}, # Natal
    'Sergipe': {'lat': -10.91667, 'lon': -37.05},      # Aracaju
    
    # --- Região Centro-Oeste ---
    'Distrito Federal': DEFAULT_FALLBACK_COORDINATES, # Brasília
    'Goiás': {'lat': -16.68689, 'lon': -49.26487},     # Goiânia
    'Mato Grosso': {'lat': -15.6014, 'lon': -56.0979},   # Cuiabá
    'Mato Grosso do Sul': {'lat': -20.4697, 'lon': -54.6201}, # Campo Grande
    
    # --- Região Sudeste ---
    'Espírito Santo': {'lat': -20.31556, 'lon': -40.31278}, # Vitória
    'Minas Gerais': {'lat': -19.91667, 'lon': -43.93333}, # Belo Horizonte
    'Rio de Janeiro': {'lat': -22.9068, 'lon': -43.1729},  # Rio de Janeiro
    'São Paulo': {'lat': -23.55052, 'lon': -46.63331},   # São Paulo
    
    # --- Região Sul ---
    'Paraná': {'lat': -25.4284, 'lon': -49.2733},      # Curitiba
    'Rio Grande do Sul': {'lat': -30.0346, 'lon': -51.2177}, # Porto Alegre
    'Santa Catarina': {'lat': -27.5969, 'lon': -48.5495}, # Florianópolis
}


def get_fallback_location(state_name: str | None) -> dict:
    """
    Obtém as coordenadas de fallback para um determinado estado.

    Se o 'state_name' for fornecido e encontrado no mapa, retorna as
    coordenadas da capital daquele estado.

    Caso contrário (None, vazio, ou não encontrado), retorna as
    coordenadas padrão (Brasília-DF).

    Argumentos:
        state_name (str | None): O nome do estado (ex: "Santa Catarina").

    Retorna:
        dict: Um dicionário com as chaves 'lat' e 'lon'.
    """
    if not state_name:
        # Se state_name é None ou uma string vazia
        return DEFAULT_FALLBACK_COORDINATES
    
    # Normaliza o nome do estado (ex: "são paulo " -> "São Paulo")
    # Isso torna a busca no dicionário mais robusta
    normalized_name = state_name.strip().title()
    
    # .get() tenta encontrar a chave; se falhar, retorna o valor padrão
    return _STATE_FALLBACK_COORDINATES.get(normalized_name, DEFAULT_FALLBACK_COORDINATES)