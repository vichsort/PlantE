from celery import shared_task
from app.extensions import db
from app.models.database import UserPlant, User, PlantGuide
from datetime import datetime, timedelta

# (Vamos criar um placeholder para o serviço de push)
# from app.services.push_notification_service import send_push_to_user

@shared_task(name="tasks.check_all_plants_for_watering")
def check_all_plants_for_watering():
    """
    TAREFA PRINCIPAL (agendada pelo Beat): Roda uma vez por dia.
    Busca todas as plantas que precisam de rega e dispara "micro-tarefas".
    """
    print("--- [CELERY BEAT]: Iniciando verificação diária de rega... ---")
    
    try:
        # A Query Mágica! Leve, eficiente, como planejamos.
        plants_to_check = db.session.query(
            UserPlant, User.fcm_token, PlantGuide.details_cache
        ).join(User, UserPlant.user_id == User.id
        ).join(PlantGuide, UserPlant.plant_entity_id == PlantGuide.entity_id
        ).filter(
            UserPlant.tracked_watering == True,    # 1. Só as plantas monitoradas
            User.fcm_token.isnot(None),            # 2. Só usuários com token de push
            PlantGuide.details_cache.isnot(None)   # 3. Só plantas que já têm dados do Gemini
        ).all()

        print(f"--- [CELERY BEAT]: Encontradas {len(plants_to_check)} plantas para verificar.")

        for user_plant, fcm_token, details_cache in plants_to_check:
            
            # Pega a frequência de rega que salvamos do Gemini
            # (Precisamos adicionar 'watering_frequency_days' ao Gemini/PlantGuide)
            frequency_days = details_cache.get('watering_frequency_days', 7) # Padrão de 7 dias se falhar
            
            # Se a planta nunca foi regada, usa a data que foi adicionada
            last_watered_date = user_plant.last_watered or user_plant.added_at
            
            # Calcula quando ela deveria ser regada
            due_date = last_watered_date.date() + timedelta(days=frequency_days)
            
            if datetime.utcnow().date() >= due_date:
                # A planta está atrasada!
                print(f"--- [CELERY BEAT]: Planta {user_plant.nickname} precisa de rega. Disparando notificação.")
                
                # Dispara a "micro-tarefa" para não travar este loop
                send_watering_notification.delay(
                    fcm_token=fcm_token,
                    plant_name=user_plant.nickname or user_plant.plant_info.scientific_name
                )
    except Exception as e:
        print(f"--- [CELERY BEAT]: ERRO na verificação diária: {e} ---")
    finally:
        db.session.remove()


@shared_task(name="tasks.send_watering_notification")
def send_watering_notification(fcm_token, plant_name):
    """
    MICRO-TAREFA (executada pelo Worker): Apenas envia uma notificação.
    """
    try:
        title = "Plante - Lembrete de Rega 💧"
        body = f"Sua planta '{plant_name}' está com sede! Não se esqueça de regá-la."
        
        # --- PLACEHOLDER ---
        # Aqui você chamaria seu serviço de FCM:
        # send_push_to_user(fcm_token, title, body)
        print(f"--- [CELERY WORKER]: ENVIANDO PUSH para {fcm_token[:10]}... sobre '{plant_name}' ---")
        
    except Exception as e:
        print(f"--- [CELERY WORKER]: Falha ao enviar push. Erro: {e} ---")

# (Aqui adicionaremos os workers 'enrich_details_data' etc. no futuro)