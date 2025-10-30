import json
from flask import Blueprint, request, current_app
from werkzeug.exceptions import BadRequest, NotFound
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.database import User, PlantGuide, UserPlant
from app.services.plant_id_service import PlantIdService
from app.utils.response_utils import make_success_response, make_error_response
from app.utils.security_utils import check_daily_limit
from app.tasks import enrich_plant_details_task, enrich_health_data_task
from datetime import datetime
from app.utils.achievement_utils import grant_achievement_if_not_exists, update_watering_streak
from app.utils.location_utils import get_fallback_location


# Define o tempo de vida do cache em segundos (7 dias)
CACHE_TTL = 60 * 60 * 24 * 7

garden_bp = Blueprint('garden_bp', __name__, url_prefix='/api/v1/garden')


def _get_guide_data(entity_id: str) -> dict | None:
    """
    Função auxiliar "burra": busca dados do guia botânico APENAS
    no cache (Redis -> Postgres). Retorna None se não encontrar.
    NÃO CHAMA O GEMINI.
    """
    
    # Tenta no Redis
    try:
        cached_guide = current_app.redis_client.get(f"guide:{entity_id}")
        if cached_guide:
            return json.loads(cached_guide)
    except Exception as e:
        current_app.logger.error(f"Erro ao acessar o cache Redis: {e}")
        # Continua para o DB se o Redis falhar

    # Tenta no Postgres
    guide_from_db = PlantGuide.query.get(entity_id)
    
    # Verifica se os caches no DB estão preenchidos
    if guide_from_db and guide_from_db.details_cache and guide_from_db.nutritional_cache:
        plant_guide_data = {
            "details": guide_from_db.details_cache,
            "nutritional": guide_from_db.nutritional_cache
        }
        
        # Re-popula o cache do Redis (se falhou ou estava vazio)
        try:
            current_app.redis_client.set(f"guide:{entity_id}", json.dumps(plant_guide_data), ex=CACHE_TTL)
        except Exception as e:
            current_app.logger.error(f"Erro ao repopular o cache Redis: {e}")

        return plant_guide_data
    
    # Cache MISS total (ou caches do DB estão vazios)
    return None


@garden_bp.route('/identify', methods=['POST'])
@jwt_required()
def identify_and_add_plant():
    """
    Endpoint de identificação: recebe imagem e localização (opcional),
    identifica, salva a URL da imagem e adiciona ao jardim.
    """
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        if not user:
             raise NotFound("Usuário não encontrado.")
        data = request.get_json() 
        image_b64 = data.get('image')
        if not image_b64:
            raise BadRequest("A imagem (em base64) é obrigatória.")
        
        latitude = data.get('latitude')
        longitude = data.get('longitude')

        if latitude is None or longitude is None:
            current_app.logger.info(f"Localização não fornecida. Verificando perfil {user.id}...")
            
            # Chama o utilitário, passando o estado do usuário
            fallback_coords = get_fallback_location(user.state) 
            
            latitude = fallback_coords['lat']
            longitude = fallback_coords['lon']
            
            if user.state:
                current_app.logger.info(f"Usando fallback para o estado: {user.state}")
            else:
                current_app.logger.info("Usuário sem estado, usando fallback padrão (Brasília).")

        # Identificação da Planta
        plant_service = PlantIdService(api_key=current_app.config['PLANT_ID_API_KEY'])
        identification = plant_service.identify_plant(image_b64, latitude, longitude)
        
        best_match = identification['result']['classification']['suggestions'][0]
        entity_id = best_match['details']['entity_id']
        scientific_name = best_match['name']
        
        # Extrai a URL da imagem do Plant.id
        image_url_from_plantid = identification.get('input', {}).get('images', [None])[0]

        # Salva no Guia Global (se não existir)
        guide_from_db = PlantGuide.query.get(entity_id)
        if not guide_from_db:
            guide_from_db = PlantGuide(
                entity_id=entity_id,
                scientific_name=scientific_name
                # Caches 'details', 'nutritional', 'health' começam como NULL
            )
            db.session.add(guide_from_db)

        user_plant = UserPlant.query.filter_by(user_id=current_user_id, plant_entity_id=entity_id).first()
        if not user_plant:
            # --- LÓGICA DE CONQUISTA ---
            # Verifica o número de plantas ANTES de adicionar a nova
            plant_count = user.garden.count()
            if plant_count == 0:
                grant_achievement_if_not_exists(user, 'first_plant')
            if plant_count == 9:
                grant_achievement_if_not_exists(user, 'ten_plants')

        # Salva no Jardim do Usuário
        user_plant = UserPlant.query.filter_by(user_id=current_user_id, plant_entity_id=entity_id).first()
        if not user_plant:
            user_plant = UserPlant(
                user_id=current_user_id,
                plant_entity_id=entity_id,
                nickname=scientific_name,
                primary_image_url=image_url_from_plantid
            )
            db.session.add(user_plant)
        else:
            # Se já tem a planta, atualiza a imagem principal
            user_plant.primary_image_url = image_url_from_plantid
        
        db.session.commit()

        final_response = {
            "user_plant_id": user_plant.id,
            "nickname": user_plant.nickname,
            "scientific_name": scientific_name,
            "tracked_watering": user_plant.tracked_watering,
            "primary_image_url": user_plant.primary_image_url,
            "identification_data": identification
        }
        
        return make_success_response(final_response, "Planta identificada e adicionada ao seu jardim.", 201)

    except BadRequest as e:
        db.session.rollback()
        return make_error_response(str(e), "BAD_REQUEST", 400)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro em /identify: {e}")
        return make_error_response(f"Ocorreu um erro interno ao processar a planta.", "INTERNAL_SERVER_ERROR", 500)


@garden_bp.route('/plants', methods=['GET'])
@jwt_required()
def get_user_plants():
    """Retorna todas as plantas do jardim do usuário."""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        plants_list = []
        for plant in user.garden.all():
            plants_list.append({
                "id": plant.id,
                "nickname": plant.nickname,
                "scientific_name": plant.plant_info.scientific_name,
                "last_watered": plant.last_watered.isoformat() if plant.last_watered else None,
                "tracked_watering": plant.tracked_watering,
                "primary_image_url": plant.primary_image_url 
            })
            
        return make_success_response(plants_list, "Jardim carregado com sucesso.")
    except Exception as e:
        current_app.logger.error(f"Erro em /plants: {e}")
        return make_error_response("Erro ao carregar o jardim.", "INTERNAL_SERVER_ERROR", 500)


@garden_bp.route('/plants/<uuid:plant_id>', methods=['GET'])
@jwt_required()
def get_plant_details(plant_id):
    """Busca os detalhes de uma planta específica no jardim do usuário."""
    try:
        current_user_id = get_jwt_identity()
        user_plant = UserPlant.query.filter_by(id=plant_id, user_id=current_user_id).first()
        
        if not user_plant:
            raise NotFound("Planta não encontrada no seu jardim.")

        guide_from_db = user_plant.plant_info

        response_data = {
            "id": user_plant.id,
            "nickname": user_plant.nickname,
            "scientific_name": guide_from_db.scientific_name,
            "added_at": user_plant.added_at.isoformat(),
            "last_watered": user_plant.last_watered.isoformat() if user_plant.last_watered else None,
            "care_notes": user_plant.care_notes,
            "tracked_watering": user_plant.tracked_watering,
            "primary_image_url": user_plant.primary_image_url,
            "has_details": guide_from_db.details_cache is not None,
            "has_nutritional": guide_from_db.nutritional_cache is not None,
            "has_health_info": guide_from_db.health_cache is not None,
            
            # para o flutter / json de guide
            "guide_details": guide_from_db.details_cache,
            "guide_nutritional": guide_from_db.nutritional_cache,
            "guide_health": guide_from_db.health_cache
        }
        
        return make_success_response(response_data, "Detalhes da planta carregados.")
    except NotFound as e:
        return make_error_response(str(e), "NOT_FOUND", 404)
    except Exception as e:
        current_app.logger.error(f"Erro em /plants/<id>: {e}")
        return make_error_response(f"Ocorreu um erro interno.", "INTERNAL_SERVER_ERROR", 500)


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
        
        if 'nickname' in data:
            user_plant.nickname = data['nickname']
        if 'last_watered' in data:
            user_plant.last_watered = datetime.fromisoformat(data['last_watered']) if data['last_watered'] else None
        if 'care_notes' in data:
            user_plant.care_notes = data['care_notes']

        if 'last_watered' in data:
            user_plant.last_watered = datetime.fromisoformat(data['last_watered']) if data['last_watered'] else None
            # Dispara um worker para recalcular o streak e conceder badges
            update_watering_streak.delay(user_id=current_user_id)
            
        db.session.commit()
        
        response_data = {
            "id": user_plant.id,
            "nickname": user_plant.nickname,
            "last_watered": user_plant.last_watered.isoformat() if user_plant.last_watered else None,
            "care_notes": user_plant.care_notes,
            "tracked_watering": user_plant.tracked_watering
        }
        
        return make_success_response(response_data, "Planta atualizada com sucesso.")
    except NotFound as e:
        return make_error_response(str(e), "NOT_FOUND", 404)
    except (ValueError, TypeError):
        return make_error_response("Formato de data inválido para 'last_watered'. Use o formato ISO.", "BAD_REQUEST", 400)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro em PUT /plants/<id>: {e}")
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
        current_app.logger.error(f"Erro em DELETE /plants/<id>: {e}")
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


# --- ENDPOINTS PREMIUM ---

@garden_bp.route('/plants/<uuid:plant_id>/analyze-deep', methods=['POST'])
@jwt_required()
@check_daily_limit(limit=3)
def trigger_deep_analysis(plant_id):
    """
    Aciona o worker Celery para buscar detalhes e dados nutricionais (Gemini).
    """
    try:
        current_user_id = get_jwt_identity()
        user_plant = UserPlant.query.filter_by(id=plant_id, user_id=current_user_id).first()
        
        if not user_plant:
            raise NotFound("Planta não encontrada no seu jardim.")
        
        guide = user_plant.plant_info
        
        if guide.details_cache and guide.nutritional_cache:
            return make_success_response(None, "Análise profunda já concluída.", 200)

        # Dispara a tarefa assíncrona
        enrich_plant_details_task.delay(
            entity_id=guide.entity_id,
            scientific_name=guide.scientific_name,
            user_id_to_notify=current_user_id
        )
        
        return make_success_response(None, "Solicitação de análise profunda recebida. Você será notificado.", 202)

    except NotFound as e:
        return make_error_response(str(e), "NOT_FOUND", 404)
    except Exception as e:
        current_app.logger.error(f"Erro em /analyze-deep: {e}")
        return make_error_response(f"Ocorreu um erro interno: {str(e)}", "INTERNAL_SERVER_ERROR", 500)


@garden_bp.route('/plants/<uuid:plant_id>/analyze-health', methods=['POST'])
@jwt_required()
@check_daily_limit(limit=3)
def trigger_health_analysis(plant_id):
    """
    Recebe UMA NOVA imagem, faz avaliação no Plant.id e dispara 
    worker do Gemini se encontrar doença.
    """
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        image_b64 = data.get('image')

        if not image_b64:
            raise BadRequest("A imagem (em base64) é obrigatória para análise de saúde.")
        
        latitude = data.get('latitude')
        longitude = data.get('longitude')

        user_plant = UserPlant.query.filter_by(id=plant_id, user_id=current_user_id).first()
        if not user_plant:
            raise NotFound("Planta não encontrada no seu jardim.")
            
        guide = user_plant.plant_info
        
        plant_service = PlantIdService(api_key=current_app.config['PLANT_ID_API_KEY'])
        health_assessment = plant_service.assess_health(image_b64, latitude, longitude)

        diseases = health_assessment.get('result', {}).get('disease', {}).get('suggestions', [])
        
        high_prob_disease = None
        for disease in diseases:
            if disease.get('probability', 0) > 0.2:
                high_prob_disease = disease
                break
        
        if not high_prob_disease:
            return make_success_response(
                {"health_assessment": health_assessment, "status": "HEALTHY"},
                "Análise de saúde concluída. Nenhuma doença provável detectada."
            )

        disease_name = high_prob_disease['name']

        if guide.health_cache and guide.health_cache.get('disease_name') == disease_name:
             return make_success_response(
                {"health_assessment": health_assessment, "status": "COMPLETED", "cached_plan": guide.health_cache},
                "Plano de tratamento para esta doença já foi gerado."
            )
        
        # Dispara o Worker Celery
        enrich_health_data_task.delay(
            entity_id=guide.entity_id,
            scientific_name=guide.scientific_name,
            disease_name=disease_name,
            user_id_to_notify=current_user_id
        )
        
        return make_success_response(
            {"health_assessment": health_assessment, "status": "PENDING_TREATMENT_PLAN"},
            "Doença detectada. Estamos preparando seu plano de tratamento.",
            status_code=202
        )

    except BadRequest as e:
        return make_error_response(str(e), "BAD_REQUEST", 400)
    except NotFound as e:
        return make_error_response(str(e), "NOT_FOUND", 404)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro em /analyze-health: {e}")
        return make_error_response(f"Ocorreu um erro interno: {str(e)}", "INTERNAL_SERVER_ERROR", 500)