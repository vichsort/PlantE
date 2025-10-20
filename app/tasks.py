from celery import shared_task, chain
from flask import current_app # Para acessar config e extensões dentro das tasks
from app.extensions import db
from app.models.database import UserPlant, User, PlantGuide # <-- CORRIGIDO AQUI
from app.services.gemini_service import GeminiService
import json
from datetime import datetime, timedelta

# Define o tempo de vida do cache que será usado pela task de enrich
# Poderia ser pego do config, mas definir aqui garante que a task o conheça
DEFAULT_CACHE_TTL = 60 * 60 * 24 * 7 # 7 dias

# --- TAREFA 2: O "Detetive de Dados" ---
@shared_task(name="tasks.enrich_plant_details_task", bind=True, max_retries=3, default_retry_delay=300) # Tenta a cada 5 min
def enrich_plant_details_task(self, entity_id, scientific_name):
    """
    TAREFA DISPARADA SOB DEMANDA: Busca detalhes no Gemini e atualiza o DB/Redis.
    O 'bind=True' permite acessar 'self' para retentativas.
    """
    print(f"--- [CELERY WORKER - Enrich]: Iniciando busca de detalhes para {scientific_name} ({entity_id}) ---")
    try:
        # Garante que estamos no contexto da aplicação Flask para usar config, db, etc.
        with current_app.app_context():
            # Verifica se outro worker já fez o trabalho enquanto este estava na fila
            guide = PlantGuide.query.get(entity_id)
            if guide and guide.details_cache and guide.nutritional_cache: # Verifica ambos
                 print(f"--- [CELERY WORKER - Enrich]: Detalhes para {entity_id} já existem no DB. Abortando.")
                 # (Opcional: Poderia verificar o Redis e repopular se necessário)
                 return # Trabalho já feito!

            # Busca no Gemini (operação cara)
            gemini_service = GeminiService(api_key=current_app.config['GEMINI_API_KEY'])
            details = gemini_service.get_details_about_plant(scientific_name)
            nutritional = gemini_service.get_nutritional_details(scientific_name)

            # Extrai os dados como dicionários Python
            details_dict = details.model_dump()
            nutritional_dict = nutritional.model_dump()

            # Atualiza ou cria no PostgreSQL (NeonDB)
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

            # Atualiza o cache do Redis (combinando os dois caches)
            combined_cache_data = {
                "details": details_dict,
                "nutritional": nutritional_dict
            }
            # Usa o redis_client anexado ao app
            current_app.redis_client.set(f"guide:{entity_id}", json.dumps(combined_cache_data), ex=DEFAULT_CACHE_TTL)
            
            print(f"--- [CELERY WORKER - Enrich]: Detalhes para {entity_id} salvos com sucesso no DB e Redis. ---")

            # (Opcional: Poderia enviar um push para o usuário que disparou a task)

    except Exception as exc:
        print(f"--- [CELERY WORKER - Enrich]: ERRO ao buscar detalhes para {entity_id}: {exc} ---")
        try:
            # Tenta novamente (bind=True e max_retries cuidam disso)
             self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            print(f"--- [CELERY WORKER - Enrich]: MÁXIMO DE TENTATIVAS ATINGIDO para {entity_id}. Desistindo. ---")
        finally:
             # Garante que a sessão do DB seja limpa em caso de erro também
             with current_app.app_context():
                db.session.remove()
    finally:
         # Garante que a sessão do DB seja limpa após o sucesso
         with current_app.app_context():
            db.session.remove()


# --- TAREFA 1: O "Fiscal Diário" ---
@shared_task(name="tasks.check_all_plants_for_watering")
def check_all_plants_for_watering():
    """
    TAREFA PRINCIPAL (agendada pelo Beat): Roda uma vez por dia.
    Identifica plantas que precisam de rega. Se faltar dados, dispara o 'enrich'.
    """
    print("--- [CELERY BEAT]: Iniciando verificação diária de rega... ---")
    
    # Executa dentro do contexto da aplicação para ter acesso ao db e config
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
                PlantGuide.details_cache # Pega o cache inteiro
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
                    # Verifica se temos a chave específica da frequência
                    frequency_days = plant.details_cache.get('watering_frequency_days')

                if frequency_days is None:
                    # NÃO TEMOS A FREQUÊNCIA! Dispara o 'enrich' e PULA esta planta hoje.
                    print(f"--- [CELERY BEAT]: Planta {plant.nickname or plant.scientific_name} ({plant.entity_id}) sem dados de rega. Disparando busca no Gemini.")
                    # Dispara a outra task para buscar os dados que faltam
                    enrich_plant_details_task.delay(entity_id=plant.entity_id, scientific_name=plant.scientific_name)
                    continue # Pula para a próxima planta no loop

                # Se chegamos aqui, temos 'frequency_days'
                last_watered_date = plant.last_watered or plant.added_at
                # Garante que a data está correta, pegando apenas a parte da data
                due_date = last_watered_date.date() + timedelta(days=frequency_days)
                
                if datetime.utcnow().date() >= due_date:
                    # A planta está atrasada! Dispara a notificação.
                    plant_display_name = plant.nickname or plant.scientific_name
                    print(f"--- [CELERY BEAT]: Planta {plant_display_name} precisa de rega. Disparando notificação.")
                    send_watering_notification.delay(
                        fcm_token=plant.fcm_token,
                        plant_name=plant_display_name
                    )
        except Exception as e:
            print(f"--- [CELERY BEAT]: ERRO na verificação diária: {e} ---")
        finally:
            db.session.remove() # Limpa a sessão do DB


# --- TAREFA 3: O "Carteiro" ---
@shared_task(name="tasks.send_watering_notification")
def send_watering_notification(fcm_token, plant_name):
    """
    MICRO-TAREFA (executada pelo Worker): Apenas envia uma notificação.
    """
    # Executa dentro do contexto da aplicação se precisar de config ou extensões
    with current_app.app_context():
        try:
            title = "Plante - Lembrete de Rega 💧"
            body = f"Sua planta '{plant_name}' está com sede! Não se esqueça de regá-la."
            
            # --- PLACEHOLDER ---
            # Aqui você chamaria seu serviço de FCM:
            # push_service = PushNotificationService()
            # push_service.send(fcm_token, title, body)
            print(f"--- [CELERY WORKER - Push]: ENVIANDO PUSH para {fcm_token[:10]}... sobre '{plant_name}' ---")
            
        except Exception as e:
            print(f"--- [CELERY WORKER - Push]: Falha ao enviar push para {fcm_token[:10]}. Erro: {e} ---")