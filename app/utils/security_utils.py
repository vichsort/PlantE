from functools import wraps
from flask import current_app
from flask_jwt_extended import get_jwt_identity
from app.models.database import User 
from app.utils.response_utils import make_error_response
from datetime import datetime, time, timedelta
import redis

# --- Expiração ---
def get_seconds_until_midnight_utc() -> int:
    """Calcula quantos segundos faltam até a próxima meia-noite UTC."""
    now_utc = datetime.utcnow()
    tomorrow_midnight_utc = datetime.combine(now_utc.date() + timedelta(days=1), time.min)
    seconds_left = (tomorrow_midnight_utc - now_utc).total_seconds()
    return int(seconds_left) + 1

def check_daily_limit(limit: int = 3):
    """
    Decorador customizado que gerencia o acesso a recursos premium.
    - Permite acesso ilimitado para usuários 'premium'.
    - Permite 'limit' (ex: 3) acessos diários para usuários 'free',
      usando o Redis para rastreamento.
    
    Deve ser usado *depois* de @jwt_required().
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user_id = get_jwt_identity()
            user = User.query.get(user_id)
            
            if not user:
                return make_error_response("Usuário não encontrado.", "USER_NOT_FOUND", 404)

            # Caminho Rápido: Usuário Premium
            is_premium = False
            if user.subscription_status == 'premium':
                if user.subscription_expires_at is None or user.subscription_expires_at > datetime.utcnow():
                    is_premium = True
            
            if is_premium:
                return fn(*args, **kwargs) # Acesso total, sem rate limit

            # Caminho free: Verificar Rate Limit no Redis
            try:
                # Gera uma chave única para este usuário e este dia (UTC)
                redis_key = f"daily_premium_usage:{user_id}:{datetime.utcnow().strftime('%Y-%m-%d')}"
                current_usage = current_app.redis_client.incr(redis_key)
                
                if current_usage == 1:
                    seconds_to_expire = get_seconds_until_midnight_utc()
                    current_app.redis_client.expire(redis_key, seconds_to_expire)

                # Verificar se o limite foi excedido
                if current_usage > limit:
                    # Limite atingido!
                    return make_error_response(
                        message=f"Você atingiu seu limite diário de {limit} ações premium gratuitas. Considere assinar o Premium!",
                        error_code="DAILY_LIMIT_REACHED",
                        status_code=429
                    )
                
                return fn(*args, **kwargs)

            except redis.exceptions.ConnectionError as e:
                # Falha de segurança: Se o Redis cair, não podemos rastrear o uso.
                # Bloqueamos o acesso 'free' para proteger nossas APIs caras (Gemini).
                current_app.logger.error(f"Redis connection error during rate limit check: {e}")
                return make_error_response(
                    message="Não foi possível verificar seu limite de uso. Tente novamente mais tarde.",
                    error_code="RATE_LIMIT_CHECK_FAILED",
                    status_code=503 # 503 Service Unavailable
                )
            except Exception as e:
                # Tomara que nunca chega aqui
                current_app.logger.error(f"Unexpected error during rate limit check: {e}")
                return make_error_response(
                    message="Erro interno ao verificar seu limite de uso.",
                    error_code="INTERNAL_SERVER_ERROR",
                    status_code=500
                )
        return wrapper
    return decorator