import json
from flask import Blueprint, request, current_app
from werkzeug.exceptions import BadRequest, NotFound
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.database import User, PlantGuide, UserPlant
from app.services.plant_id_service import PlantIdService
from app.services.gemini_service import GeminiService
from app.utils.response_utils import make_success_response, make_error_response
from datetime import datetime

# Define o tempo de vida do cache em segundos (7 dias)
CACHE_TTL = 60 * 60 * 24 * 7

garden_bp = Blueprint('garden_bp', __name__, url_prefix='/api/v1/garden')


def _get_guide_data(entity_id, scientific_name):
    """
    Função auxiliar interna para buscar dados do guia botânico,
    seguindo a lógica de cache (Redis -> Postgres -> Gemini).
    Esta função NÃO dá commit no db.session.
    """
    
    # Tenta no Redis
    cached_guide = current_app.redis_client.get(f"guide:{entity_id}")
    if cached_guide:
        return json.loads(cached_guide)

    # Tenta no Postgres
    guide_from_db = PlantGuide.query.get(entity_id)
    if guide_from_db:
        plant_guide_data = {
            "details": guide_from_db.details_cache,
            "nutritional": guide_from_db.nutritional_cache
        }
        # Re-popula o cache do Redis
        current_app.redis_client.set(f"guide:{entity_id}", json.dumps(plant_guide_data), ex=CACHE_TTL)
        return plant_guide_data

    # 3. Cache MISS total: busca no Gemini
    gemini_service = GeminiService(api_key=current_app.config['GEMINI_API_KEY'])
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
    current_app.redis_client.set(f"guide:{entity_id}", json.dumps(plant_guide_data), ex=CACHE_TTL)
    
    return plant_guide_data


@garden_bp.route('/identify', methods=['POST'])
@jwt_required()
def identify_and_add_plant():
    """
    Endpoint de identificação: recebe uma imagem, identifica (Plant.id),
    e adiciona a planta ao jardim do usuário com dados mínimos.
    """
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        image_b64 = data.get('image')

        if not image_b64:
            raise BadRequest("A imagem (em base64) é obrigatória.")
        
        latitude = data.get('latitude')
        longitude = data.get('longitude')

        # --- Identificação da Planta (API Externa) ---
        plant_service = PlantIdService(api_key=current_app.config['PLANT_ID_API_KEY'])
        identification = plant_service.identify_plant(
            image_base64=image_b64,
            latitude=latitude,
            longitude=longitude
        )
        best_match = identification['result']['classification']['suggestions'][0]
        entity_id = best_match['details']['entity_id']
        scientific_name = best_match['name']

        # --- Adicionar ao Guia Global (se não existir) ---
        guide_from_db = PlantGuide.query.get(entity_id)
        if not guide_from_db:
            guide_from_db = PlantGuide(
                entity_id=entity_id,
                scientific_name=scientific_name
                # Os caches 'details', 'nutritional', 'health' começam como NULL
            )
            db.session.add(guide_from_db)

        # --- Adicionar ao Jardim do Usuário ---
        user_plant = UserPlant.query.filter_by(user_id=current_user_id, plant_entity_id=entity_id).first()
        if not user_plant:
            user_plant = UserPlant(
                user_id=current_user_id,
                plant_entity_id=entity_id,
                nickname=scientific_name # Um apelido padrão
                # 'tracked_watering' será False por padrão (definido no modelo)
            )
            db.session.add(user_plant)
        
        db.session.commit()

        # --- Resposta Final ---
        final_response = {
            "user_plant_id": user_plant.id,
            "nickname": user_plant.nickname,
            "scientific_name": scientific_name,
            "tracked_watering": user_plant.tracked_watering,
            "identification_data": identification # Retorna os dados do Plant.id
        }
        
        return make_success_response(final_response, "Planta identificada e adicionada ao seu jardim.", 201)

    except BadRequest as e:
        return make_error_response(str(e), "BAD_REQUEST", 400)
    except Exception as e:
        db.session.rollback()
        return make_error_response(f"Ocorreu um erro interno ao processar a planta: {str(e)}", "INTERNAL_SERVER_ERROR", 500)


@garden_bp.route('/plants', methods=['GET'])
@jwt_required()
def get_user_plants():
    """Retorna todas as plantas do jardim do usuário."""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    plants_list = []
    for plant in user.garden.all():
        plants_list.append({
            "id": plant.id,
            "nickname": plant.nickname,
            "scientific_name": plant.plant_info.scientific_name,
            "last_watered": plant.last_watered.isoformat() if plant.last_watered else None,
            "tracked_watering": plant.tracked_watering
        })
        
    return make_success_response(plants_list, "Jardim carregado com sucesso.")

@garden_bp.route('/plants/<uuid:plant_id>', methods=['GET'])
@jwt_required()
def get_plant_details(plant_id):
    """Busca os detalhes de uma planta específica no jardim do usuário."""
    try:
        current_user_id = get_jwt_identity()
        
        user_plant = UserPlant.query.filter_by(id=plant_id, user_id=current_user_id).first()
        
        if not user_plant:
            raise NotFound("Planta não encontrada no seu jardim.")

        # Busca os dados do guia (do cache ou db)
        guide_from_db = PlantGuide.query.get(user_plant.plant_entity_id)

        # Monta a resposta completa
        response_data = {
            "id": user_plant.id,
            "nickname": user_plant.nickname,
            "scientific_name": user_plant.plant_info.scientific_name,
            "added_at": user_plant.added_at.isoformat(),
            "last_watered": user_plant.last_watered.isoformat() if user_plant.last_watered else None,
            "care_notes": user_plant.care_notes,
            "tracked_watering": user_plant.tracked_watering,
            # Adiciona os booleanos 'has_' para o Flutter
            "has_details": guide_from_db.details_cache is not None,
            "has_nutritional": guide_from_db.nutritional_cache is not None
            # "has_health_info": guide_from_db.health_cache is not None (quando adicionarmos)
        }
        
        return make_success_response(response_data, "Detalhes da planta carregados.")

    except NotFound as e:
        return make_error_response(str(e), "NOT_FOUND", 404)
    except Exception as e:
        return make_error_response(f"Ocorreu um erro interno: {str(e)}", "INTERNAL_SERVER_ERROR", 500)


@garden_bp.route('/plants/<uuid:plant_id>', methods=['PUT'])
@jwt_required()
def update_plant_details(plant_id):
    """Atualiza os dados de uma planta no jardim do usuário (apelido, notas, etc.)."""
    try:
        current_user_id = get_jwt_identity()
        
        user_plant = UserPlant.query.filter_by(id=plant_id, user_id=current_user_id).first()
        
        if not user_plant:
            raise NotFound("Planta não encontrada no seu jardim.")
            
        data = request.get_json()
        
        # Atualiza apenas os campos permitidos (não 'tracked_watering')
        if 'nickname' in data:
            user_plant.nickname = data['nickname']
        
        if 'last_watered' in data:
            user_plant.last_watered = datetime.fromisoformat(data['last_watered']) if data['last_watered'] else None
        
        if 'care_notes' in data:
            user_plant.care_notes = data['care_notes']
            
        db.session.commit()
        
        # Retorna os dados atualizados
        response_data = {
            "id": user_plant.id,
            "nickname": user_plant.nickname,
            "last_watered": user_plant.last_watered.isoformat() if user_plant.last_watered else None,
            "care_notes": user_plant.care_notes,
            "tracked_watering": user_plant.tracked_watering # Retorna o estado atual
        }
        
        return make_success_response(response_data, "Planta atualizada com sucesso.")

    except NotFound as e:
        return make_error_response(str(e), "NOT_FOUND", 404)
    except (ValueError, TypeError):
        return make_error_response("Formato de data inválido para 'last_watered'. Use o formato ISO.", "BAD_REQUEST", 400)
    except Exception as e:
        db.session.rollback()
        return make_error_response(f"Ocorreu um erro interno: {str(e)}", "INTERNAL_SERVER_ERROR", 500)


@garden_bp.route('/plants/<uuid:plant_id>', methods=['DELETE'])
@jwt_required()
def delete_plant(plant_id):
    """Remove uma planta do jardim do usuário."""
    try:
        current_user_id = get_jwt_identity()
        
        user_plant = UserPlant.query.filter_by(id=plant_id, user_id=current_user_id).first()
        
        if not user_plant:
            raise NotFound("Planta não encontrada no seu jardim.")
        
        db.session.delete(user_plant)
        db.session.commit()
        
        return make_success_response(None, "Planta removida do seu jardim com sucesso.")

    except NotFound as e:
        return make_error_response(str(e), "NOT_FOUND", 404)
    except Exception as e:
        db.session.rollback()
        return make_error_response(f"Ocorreu um erro interno: {str(e)}", "INTERNAL_SERVER_ERROR", 500)
    
@garden_bp.route('/plants/<uuid:plant_id>/track-watering', methods=['POST'])
@jwt_required()
def track_plant_watering(plant_id):
    """Ativa o monitoramento de rega para uma planta específica."""
    try:
        current_user_id = get_jwt_identity()
        user_plant = UserPlant.query.filter_by(id=plant_id, user_id=current_user_id).first()
        
        if not user_plant:
            raise NotFound("Planta não encontrada no seu jardim.")
        
        user_plant.tracked_watering = True
        db.session.commit()
        
        return make_success_response(
            {"tracked_watering": user_plant.tracked_watering},
            "Monitoramento de rega ativado."
        )
        
    except NotFound as e:
        return make_error_response(str(e), "NOT_FOUND", 404)
    except Exception as e:
        db.session.rollback()
        return make_error_response(f"Ocorreu um erro interno: {str(e)}", "INTERNAL_SERVER_ERROR", 500)

@garden_bp.route('/plants/<uuid:plant_id>/track-watering', methods=['DELETE'])
@jwt_required()
def untrack_plant_watering(plant_id):
    """Desativa o monitoramento de rega para uma planta específica."""
    try:
        current_user_id = get_jwt_identity()
        user_plant = UserPlant.query.filter_by(id=plant_id, user_id=current_user_id).first()
        
        if not user_plant:
            raise NotFound("Planta não encontrada no seu jardim.")
        
        user_plant.tracked_watering = False
        db.session.commit()
        
        return make_success_response(
            {"tracked_watering": user_plant.tracked_watering},
            "Monitoramento de rega desativado."
        )
        
    except NotFound as e:
        return make_error_response(str(e), "NOT_FOUND", 404)
    except Exception as e:
        db.session.rollback()
        return make_error_response(f"Ocorreu um erro interno: {str(e)}", "INTERNAL_SERVER_ERROR", 500)