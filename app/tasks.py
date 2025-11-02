from celery import shared_task
from flask import current_app
from app.extensions import db
from app.models.database import UserPlant, User, PlantGuide 
from app.services.gemini_service import GeminiService
import json
from datetime import datetime, timedelta
from app.utils.achievement_utils import grant_achievement_if_not_exists

# Define o tempo de vida do cache que será usado pela task de enrich
DEFAULT_CACHE_TTL = 60 * 60 * 24 * 7 # 7 dias

# Busca no gemini
@shared_task(name="tasks.enrich_plant_details_task", bind=True, max_retries=3, default_retry_delay=300)
def enrich_plant_details_task(self, entity_id, scientific_name, user_id_to_notify: str):
    """
    TAREFA DISPARADA SOB DEMANDA: Busca detalhes no Gemini e atualiza o DB/Redis.
    Também concede a conquista 'first_deep_analysis'.
    """
    print(f"--- [CELERY WORKER - Enrich]: Iniciando busca de detalhes para {scientific_name} ({entity_id}) ---")
    try:
        with current_app.app_context():
            guide = PlantGuide.query.get(entity_id)
            if guide and guide.details_cache and guide.nutritional_cache:
                 print(f"--- [CELERY WORKER - Enrich]: Detalhes para {entity_id} já existem no DB. Abortando.")
                 return

            gemini_service = GeminiService(api_key=current_app.config['GEMINI_API_KEY'])
            details = gemini_service.get_details_about_plant(scientific_name)
            nutritional = gemini_service.get_nutritional_details(scientific_name)

            details_dict = details.model_dump()
            nutritional_dict = nutritional.model_dump()

            if guide:
                guide.details_cache = details_dict
                guide.nutritional_cache = nutritional_dict
                guide.last_gemini_update = datetime.utcnow()
            else:
                 guide = PlantGuide(
                     entity_id=entity_id,
                     scientific_name=scientific_name,
                     details_cache=details_dict,
                     nutritional_cache=nutritional_dict,
                     last_gemini_update = datetime.utcnow()
                 )
                 db.session.add(guide)
            
            user = User.query.get(user_id_to_notify)
            if user:
                grant_achievement_if_not_exists(user, 'first_deep_analysis')

            db.session.commit()

            user = User.query.get(user_id_to_notify)
            if user and user.fcm_token:
                send_generic_push.delay(
                    fcm_token=user.fcm_token,
                    title="Análise Concluída!",
                    body=f"Os detalhes profundos da sua '{guide.scientific_name}' estão prontos.",
                    data={
                        "navigation_type": "plant_detail",
                        "plant_id": str(user.garden.filter_by(plant_entity_id=guide.entity_id).first().id)
                    }
                )

            combined_cache_data = {
                "details": details_dict,
                "nutritional": nutritional_dict
            }
            current_app.redis_client.set(f"guide:{entity_id}", json.dumps(combined_cache_data), ex=DEFAULT_CACHE_TTL)
            
            print(f"--- [CELERY WORKER - Enrich]: Detalhes para {entity_id} salvos com sucesso no DB e Redis. ---")

    except Exception as exc:
        print(f"--- [CELERY WORKER - Enrich]: ERRO ao buscar detalhes para {entity_id}: {exc} ---")
        db.session.rollback() # Garante rollback em caso de erro
        try:
             self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            print(f"--- [CELERY WORKER - Enrich]: MÁXIMO DE TENTATIVAS ATINGIDO para {entity_id}. Desistindo. ---")
        finally:
             with current_app.app_context():
                db.session.remove()
    finally:
         with current_app.app_context():
            db.session.remove()

# Verifica rega
@shared_task(name="tasks.check_all_plants_for_watering")
def check_all_plants_for_watering():
    """
    TAREFA PRINCIPAL (agendada pelo Beat): Roda uma vez por dia.
    Identifica plantas que precisam de rega. Se faltar dados, dispara o 'enrich'.
    """
    print("--- [CELERY BEAT]: Iniciando verificação diária de rega... ---")
    
    with current_app.app_context():
        try:
            plants_to_check = db.session.query(
                UserPlant.id.label('user_plant_id'),
                UserPlant.nickname,
                UserPlant.last_watered,
                UserPlant.added_at,
                User.id.label('user_id'),
                User.fcm_token,
                PlantGuide.entity_id,
                PlantGuide.scientific_name,
                PlantGuide.details_cache
            ).join(User, UserPlant.user_id == User.id
            ).join(PlantGuide, UserPlant.plant_entity_id == PlantGuide.entity_id
            ).filter(
                UserPlant.tracked_watering == True,
                User.fcm_token.isnot(None)
            ).all()

            print(f"--- [CELERY BEAT]: Encontradas {len(plants_to_check)} plantas monitoradas para verificar.")

            for plant in plants_to_check:
                frequency_days = None
                
                if plant.details_cache and isinstance(plant.details_cache, dict):
                    frequency_days = plant.details_cache.get('watering_frequency_days')

                if frequency_days is None:
                    print(f"--- [CELERY BEAT]: Planta {plant.nickname or plant.scientific_name} ({plant.entity_id}) sem dados de rega. Disparando busca no Gemini.")
                    enrich_plant_details_task.delay(
                        entity_id=plant.entity_id, 
                        scientific_name=plant.scientific_name,
                        user_id_to_notify=plant.user_id
                    )
                    continue 

                last_watered_date = plant.last_watered or plant.added_at
                due_date = last_watered_date.date() + timedelta(days=frequency_days)
                
                if datetime.utcnow().date() >= due_date:
                    plant_display_name = plant.nickname or plant.scientific_name
                    print(f"--- [CELERY BEAT]: Planta {plant_display_name} precisa de rega. Disparando notificação.")
                    send_watering_notification.delay(
                        fcm_token=plant.fcm_token,
                        plant_name=plant_display_name,
                        plant_id=str(plant.user_plant_id)
                    )
        except Exception as e:
            print(f"--- [CELERY BEAT]: ERRO na verificação diária: {e} ---")
            db.session.rollback()
        finally:
            db.session.remove()

# Envia notificacao
@shared_task(name="tasks.send_watering_notification")
def send_watering_notification(fcm_token, plant_name, plant_id: str):
    """
    MICRO-TAREFA: Envia uma notificação de rega e trata erros FCM.
    """
    with current_app.app_context():
        try:
            title = "Plante - Lembrete de Rega"
            body = f"Sua planta '{plant_name}' está com sede! Não se esqueça de regá-la."

            navigation_data = {
                "navigation_type": "plant_detail",
                "plant_id": plant_id
            }
            
            print(f"--- [CELERY WORKER - Push]: ENVIANDO PUSH para {fcm_token[:10]}... sobre '{plant_name}' ---")

            # testando
            from app.services.push_notification_service import send_push_to_token
            send_push_to_token(fcm_token, title, body, data=navigation_data)
            
        except Exception as e: 
            print(f"--- [CELERY WORKER - Push]: Falha GERAL ao enviar push para {fcm_token[:10]}. Erro: {e} ---")

# TOKENS
@shared_task(name="tasks.invalidate_fcm_token", bind=True, max_retries=3, default_retry_delay=60)
def invalidate_fcm_token(self, fcm_token_to_remove):
    """
    TAREFA DISPARADA SOB DEMANDA: Define fcm_token = None para um token específico.
    """
    print(f"--- [CELERY WORKER - Invalidate]: Tentando invalidar token {fcm_token_to_remove[:10]}... ---")
    with current_app.app_context():
        try:
            user = User.query.filter_by(fcm_token=fcm_token_to_remove).first()
            
            if user:
                print(f"--- [CELERY WORKER - Invalidate]: Token encontrado para user {user.id}. Invalidando.")
                user.fcm_token = None
                user.fcm_token_updated_at = None
                db.session.commit()
            else:
                print(f"--- [CELERY WORKER - Invalidate]: Token {fcm_token_to_remove[:10]}... não encontrado ou já invalidado.")
                
        except Exception as exc:
            print(f"--- [CELERY WORKER - Invalidate]: ERRO ao invalidar token: {exc} ---")
            db.session.rollback()
            self.retry(exc=exc)
        finally:
            db.session.remove()

@shared_task(name="tasks.check_stale_fcm_tokens")
def check_stale_fcm_tokens():
    """
    TAREFA AGENDADA (ex: semanal): Busca por tokens FCM que não foram atualizados
    há muito tempo e dispara a invalidação para eles.
    """
    print("--- [CELERY BEAT - Stale Check]: Iniciando verificação de tokens FCM antigos... ---")
    STALE_DAYS = 60 # Define o que é "antigo" (ex: 60 dias)
    
    with current_app.app_context():
        try:
            stale_threshold = datetime.utcnow() - timedelta(days=STALE_DAYS)
            
            stale_users = User.query.filter(
                User.fcm_token.isnot(None),
                User.fcm_token_updated_at < stale_threshold
            ).all()

            print(f"--- [CELERY BEAT - Stale Check]: Encontrados {len(stale_users)} tokens potencialmente antigos.")

            for user in stale_users:
                print(f"--- [CELERY BEAT - Stale Check]: Token do user {user.id} ({user.fcm_token[:10]}...) parece antigo. Disparando invalidação.")
                invalidate_fcm_token.delay(fcm_token_to_remove=user.fcm_token)
                    
        except Exception as e:
            print(f"--- [CELERY BEAT - Stale Check]: ERRO na verificação de tokens antigos: {e} ---")
        finally:
            db.session.remove()

# Saude gemini
@shared_task(name="tasks.enrich_health_data_task", bind=True, max_retries=3, default_retry_delay=300)
def enrich_health_data_task(self, entity_id: str, scientific_name: str, disease_name: str, user_id_to_notify: str):
    """
    TAREFA DISPARADA SOB DEMANDA: Busca o plano de tratamento de doença no Gemini.
    """
    print(f"--- [CELERY WORKER - Health]: Buscando plano de tratamento para {disease_name} em {scientific_name} ---")
    
    try:
        with current_app.app_context():
            guide = PlantGuide.query.get(entity_id)
            if not guide:
                print(f"--- [CELERY WORKER - Health]: PlantGuide {entity_id} não encontrado. Abortando.")
                return

            if guide.health_cache and guide.health_cache.get('disease_name') == disease_name:
                print(f"--- [CELERY WORKER - Health]: Plano de tratamento para {disease_name} já existe. Abortando.")
                return

            gemini_service = GeminiService(api_key=current_app.config['GEMINI_API_KEY'])
            treatment_plan = gemini_service.get_disease_treatment_plan(scientific_name, disease_name)
            
            health_data = treatment_plan.model_dump()

            guide.health_cache = health_data
            guide.last_gemini_update = datetime.utcnow()
            db.session.commit()

            user = User.query.get(user_id_to_notify)
            if user and user.fcm_token:
                send_generic_push.delay(
                    fcm_token=user.fcm_token,
                    title="Plano de Saúde Pronto!",
                    body=f"O plano de tratamento para '{disease_name}' na sua '{guide.scientific_name}' está pronto.",
                    data={
                        "navigation_type": "plant_detail",
                        "plant_id": str(user.garden.filter_by(plant_entity_id=guide.entity_id).first().id)
                    }
                )

            print(f"--- [CELERY WORKER - Health]: Plano de tratamento para {disease_name} salvo com sucesso. ---")
            
    except Exception as exc:
        print(f"--- [CELERY WORKER - Health]: ERRO ao buscar plano de tratamento: {exc} ---")
        db.session.rollback()
        try:
             self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            print(f"--- [CELERY WORKER - Health]: MÁXIMO DE TENTATIVAS ATINGIDO para {entity_id}. Desistindo. ---")
        finally:
             with current_app.app_context():
                db.session.remove()
    finally:
         with current_app.app_context():
            db.session.remove()


@shared_task(name="tasks.send_generic_push")
def send_generic_push(fcm_token: str, title: str, body: str, data: dict = None):
    """Envia uma notificação push genérica."""
    with current_app.app_context():
        try:
            from app.services.push_notification_service import send_push_to_token
            send_push_to_token(fcm_token, title, body, data)
        except Exception as e:
            print(f"--- [CELERY WORKER - Push Genérico]: Falha ao enviar push: {e} ---")

# Games
@shared_task(name="tasks.update_watering_streak", bind=True)
def update_watering_streak(self, user_id: str):
    """
    (Lógica Simplificada) Recalcula o streak de rega do usuário e concede badges.
    Disparado após o usuário registrar uma rega (PUT /plants/<id>).
    """
    print(f"--- [CELERY WORKER - Streak]: Atualizando streak para {user_id} ---")
    with current_app.app_context():
        try:
            user = User.query.get(user_id)
            if not user:
                return

            user.watering_streak = (user.watering_streak or 0) + 1
            streak = user.watering_streak
            
            print(f"--- [CELERY WORKER - Streak]: Novo streak: {streak} dias ---")

            if streak >= 365:
                grant_achievement_if_not_exists(user, 'streak_1_year')
            elif streak >= 180:
                grant_achievement_if_not_exists(user, 'streak_6_months')
            elif streak >= 90:
                grant_achievement_if_not_exists(user, 'streak_3_months')
            elif streak >= 30:
                grant_achievement_if_not_exists(user, 'streak_1_month')
            
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro ao atualizar streak: {e}")
        finally:
            db.session.remove()

@shared_task(name="tasks.check_user_longevity")
def check_user_longevity():
    """
    TAREFA AGENDADA (ex: diária): Verifica a longevidade do usuário e da assinatura.
    """
    print("--- [CELERY BEAT - Longevity]: Verificando longevidade dos usuários... ---")
    with current_app.app_context():
        try:
            now = datetime.utcnow()
            users = User.query.all()
            
            for user in users:
                days_since_creation = (now - user.created_at).days
                
                # Concessão de longevidade de conta
                if days_since_creation >= 365:
                    grant_achievement_if_not_exists(user, 'user_1_year')
                elif days_since_creation >= 180:
                    grant_achievement_if_not_exists(user, 'user_6_months')
                elif days_since_creation >= 90:
                    grant_achievement_if_not_exists(user, 'user_3_months')

                if user.subscription_status == 'premium' and user.subscription_expires_at:
                    days_as_premium = (now - (user.subscription_expires_at - timedelta(days=30))).days
                    if days_as_premium >= 365:
                         grant_achievement_if_not_exists(user, 'premium_1_year')
                    elif days_as_premium >= 180:
                         grant_achievement_if_not_exists(user, 'premium_6_months')
                    elif days_as_premium >= 90:
                         grant_achievement_if_not_exists(user, 'premium_3_months')
            
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Erro na verificação de longevidade: {e}")
        finally:
            db.session.remove()