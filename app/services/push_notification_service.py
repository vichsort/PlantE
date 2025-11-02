"""
Serviços agenciadores do firebase messaging
para permitir mandar as notificações no app
de maneira controlada
"""

from firebase_admin import messaging
from app.tasks import invalidate_fcm_token

def send_push_to_token(fcm_token: str, title: str, body: str, data: dict = None):
    try:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            token=fcm_token,
            data=data
        )
        messaging.send(message)
        print(f"PUSH: Enviado com sucesso para {fcm_token[:10]}...")
    except messaging.UnregisteredError:
        print(f"PUSH ERROR: Token {fcm_token[:10]}... não registrado. Disparando limpeza.")
        invalidate_fcm_token.delay(fcm_token_to_remove=fcm_token)
    except Exception as e:
        print(f"PUSH ERROR: Falha geral ao enviar: {e}")