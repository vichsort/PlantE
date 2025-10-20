from functools import wraps
from flask_jwt_extended import get_jwt_identity
from app.models.database import User
from app.utils.response_utils import make_error_response
from datetime import datetime

def premium_required(fn):
    """
    Um decorador customizado que verifica se o usuário
    logado possui uma subscrição 'premium' ativa.
    Deve ser usado *depois* de @jwt_required().
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        is_premium = False
        if user and user.subscription_status == 'premium':
            # Verifica se a subscrição expirou
            if user.subscription_expires_at is None or user.subscription_expires_at > datetime.utcnow():
                is_premium = True
        
        if not is_premium:
            return make_error_response(
                message="Este recurso é exclusivo para membros Premium.",
                error_code="FORBIDDEN_PREMIUM_REQUIRED",
                status_code=403 # 403 Forbidden
            )
        return fn(*args, **kwargs)
    return wrapper