import json
from flask import Blueprint, request
from werkzeug.exceptions import BadRequest
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db, redis_client
from app.models.database import User, PlantGuide, UserPlant
from app.services.plant_id_service import PlantIdService
from app.services.gemini_service import GeminiService
from app.utils.response_utils import make_success_response, make_error_response

# Define o tempo de vida do cache em segundos (7 dias)
CACHE_TTL = 60 * 60 * 24 * 7

garden_bp = Blueprint('garden_bp', __name__, url_prefix='/api/v1/garden')

@garden_bp.route('/analyze', methods=['POST'])
@jwt_required()
def analyze_and_add_plant():
    """
    Endpoint principal: recebe uma imagem, analisa, busca em caches,
    consulta APIs externas se necessário, e adiciona a planta ao jardim do usuário.
    """
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        image_b64 = data.get('image')

        if not image_b64:
            raise BadRequest("A imagem (em base64) é obrigatória.")

        # --- 1. Identificação da Planta (API Externa) ---
        plant_service = PlantIdService() # Idealmente, injetar com as chaves do app.config
        identification = plant_service.identify_plant(image_b64)
        best_match = identification['result']['classification']['suggestions'][0]
        entity_id = best_match['details']['entity_id']
        scientific_name = best_match['name']

        # --- 2. Lógica de Cache e Busca de Dados ---
        plant_guide_data = None
        
        # Tenta o cache rápido (Redis) primeiro
        cached_guide = redis_client.get(f"guide:{entity_id}")
        if cached_guide:
            plant_guide_data = json.loads(cached_guide)
        else:
            # Tenta o cache permanente (PostgreSQL)
            guide_from_db = PlantGuide.query.get(entity_id)
            if guide_from_db:
                plant_guide_data = {
                    "details": guide_from_db.details_cache,
                    "nutritional": guide_from_db.nutritional_cache
                }
                # Re-popula o cache do Redis
                redis_client.set(f"guide:{entity_id}", json.dumps(plant_guide_data), ex=CACHE_TTL)
            else:
                # Cache MISS total: busca no Gemini e salva em todos os lugares
                gemini_service = GeminiService() # Injetar chaves
                details = gemini_service.get_details_about_plant(scientific_name)
                nutritional = gemini_service.get_nutritional_details(scientific_name)

                plant_guide_data = {
                    "details": details.model_dump(),
                    "nutritional": nutritional.model_dump()
                }

                # Salva no PostgreSQL
                new_guide = PlantGuide(
                    entity_id=entity_id,
                    scientific_name=scientific_name,
                    details_cache=plant_guide_data["details"],
                    nutritional_cache=plant_guide_data["nutritional"]
                )
                db.session.add(new_guide)
                
                # Salva no Redis
                redis_client.set(f"guide:{entity_id}", json.dumps(plant_guide_data), ex=CACHE_TTL)

        # --- 3. Adicionar ao Jardim do Usuário ---
        # Verifica se o usuário já tem essa planta
        user_plant = UserPlant.query.filter_by(user_id=current_user_id, plant_entity_id=entity_id).first()
        if not user_plant:
            user_plant = UserPlant(
                user_id=current_user_id,
                plant_entity_id=entity_id,
                nickname=scientific_name # Um apelido padrão
            )
            db.session.add(user_plant)
        
        db.session.commit()

        # --- 4. Montar a Resposta Final ---
        final_response = {
            "user_plant_id": user_plant.id,
            "nickname": user_plant.nickname,
            "identification": identification,
            "guide_data": plant_guide_data
        }
        
        return make_success_response(final_response, "Planta analisada e adicionada ao seu jardim.")

    except BadRequest as e:
        return make_error_response(str(e), "BAD_REQUEST", 400)
    except Exception as e:
        db.session.rollback()
        # Idealmente, logar o erro 'e' aqui
        return make_error_response("Ocorreu um erro interno ao processar a planta.", "INTERNAL_SERVER_ERROR", 500)


@garden_bp.route('/plants', methods=['GET'])
@jwt_required()
def get_user_plants():
    """Retorna todas as plantas do jardim do usuário."""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    plants_list = []
    for plant in user.garden:
        plants_list.append({
            "id": plant.id,
            "nickname": plant.nickname,
            "scientific_name": plant.plant_info.scientific_name,
            "last_watered": plant.last_watered.isoformat() if plant.last_watered else None
        })
        
    return make_success_response(plants_list, "Jardim carregado com sucesso.")

# Adicione aqui os outros endpoints: GET <id>, PUT <id>, DELETE <id>