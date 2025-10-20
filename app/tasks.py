from celery import shared_task
from flask import current_app
from app.extensions import db
from app.models.database import UserPlant, User, PlantGuide 
from app.services.gemini_service import GeminiService
import json
from datetime import datetime, timedelta

# Define o tempo de vida do cache que será usado pela task de enrich
DEFAULT_CACHE_TTL = 60 * 60 * 24 * 7 # 7 dias

# --- TAREFA: O "Detetive de Dados" (Busca no Gemini) ---
@shared_task(name="tasks.enrich_plant_details_task", bind=True, max_retries=3, default_retry_delay=300) # Tenta a cada 5 min
def enrich_plant_details_task(self, entity_id, scientific_name):
    """
    TAREFA DISPARADA SOB DEMANDA: Busca detalhes no Gemini e atualiza o DB/Redis.
    """
    print(f"--- [CELERY WORKER - Enrich]: Iniciando busca de detalhes para {scientific_name} ({entity_id}) ---")
    try:
        # Garante que estamos no contexto da aplicação Flask
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
            
            db.session.commit()

            combined_cache_data = {
                "details": details_dict,
                "nutritional": nutritional_dict
            }
            # Usa o redis_client anexado ao app
            current_app.redis_client.set(f"guide:{entity_id}", json.dumps(combined_cache_data), ex=DEFAULT_CACHE_TTL)
            
            print(f"--- [CELERY WORKER - Enrich]: Detalhes para {entity_id} salvos com sucesso no DB e Redis. ---")

    except Exception as exc:
        print(f"--- [CELERY WORKER - Enrich]: ERRO ao buscar detalhes para {entity_id}: {exc} ---")
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

# --- TAREFA: O "Fiscal Diário" (Verifica Rega) ---
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
                    enrich_plant_details_task.delay(entity_id=plant.entity_id, scientific_name=plant.scientific_name)
                    continue 

                last_watered_date = plant.last_watered or plant.added_at
                due_date = last_watered_date.date() + timedelta(days=frequency_days)
                
                if datetime.utcnow().date() >= due_date:
                    plant_display_name = plant.nickname or plant.scientific_name
                    print(f"--- [CELERY BEAT]: Planta {plant_display_name} precisa de rega. Disparando notificação.")
                    send_watering_notification.delay(
                        fcm_token=plant.fcm_token,
                        plant_name=plant_display_name
                    )
        except Exception as e:
            print(f"--- [CELERY BEAT]: ERRO na verificação diária: {e} ---")
        finally:
            db.session.remove()

# --- TAREFA: O "Carteiro" (Envia Notificação de Rega) ---
@shared_task(name="tasks.send_watering_notification")
def send_watering_notification(fcm_token, plant_name):
    """
    MICRO-TAREFA: Envia uma notificação de rega e trata erros FCM.
    """
    with current_app.app_context():
        try:
            title = "Plante - Lembrete de Rega 💧"
            body = f"Sua planta '{plant_name}' está com sede! Não se esqueça de regá-la."
            
            print(f"--- [CELERY WORKER - Push]: ENVIANDO PUSH para {fcm_token[:10]}... sobre '{plant_name}' ---")
            # Exemplo conceitual:
            # push_service = PushNotificationService() 
            # try:
            #     push_service.send(fcm_token, title, body) 
            # except UnregisteredError as e: # Captura o erro específico de token inválido
            #     print(f"--- [CELERY WORKER - Push]: Token {fcm_token[:10]}... inválido (Unregistered). Disparando invalidação.")
            #     invalidate_fcm_token.delay(fcm_token_to_remove=fcm_token)
            # except InvalidArgumentError as e: # Outro erro comum de token mal formatado
            #     print(f"--- [CELERY WORKER - Push]: Token {fcm_token[:10]}... mal formatado. Disparando invalidação.")
            #     invalidate_fcm_token.delay(fcm_token_to_remove=fcm_token)
            # --- Fim da Lógica de Envio ---
            
        except Exception as e: 
            print(f"--- [CELERY WORKER - Push]: Falha GERAL ao enviar push para {fcm_token[:10]}. Erro: {e} ---")

# --- TAREFA: O "Limpador Reativo" (Invalida Token Após Erro FCM) ---
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
            self.retry(exc=exc)
        finally:
            db.session.remove()

# --- TAREFA: O "Limpador Proativo" (Verifica Tokens Antigos) ---
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