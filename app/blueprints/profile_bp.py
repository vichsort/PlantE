"""
Blueprints/rotas aos dados do perfil
do usuário. São:
(prefixo /api/v1/profile/)
- /me -> vê, edita dados do seu perfil
- mais virão aqui futuramente.
"""

from flask import Blueprint, request, current_app
from app.models.database import User
from app.extensions import db
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.exceptions import BadRequest, NotFound
from app.utils.response_utils import make_success_response, make_error_response

profile_bp = Blueprint('profile_bp', __name__, url_prefix='/api/v1/profile')

@profile_bp.route('/me', methods=['GET'])
@jwt_required()
def get_my_profile():
    """
    Busca e retorna os dados de perfil do usuário logado.
    Chamado pelo Flutter ao abrir a ProfileScreen.
    """
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)

        if not user:
            raise NotFound("Usuário não encontrado.")

        # Serializa os dados do perfil para enviar como JSON
        profile_data = {
            "id": user.id,
            "email": user.email,
            "bio": user.bio,
            "profile_picture_url": user.profile_picture_url,
            "country": user.country,
            "state": user.state,
            "subscription_status": user.subscription_status,
            "subscription_expires_at": user.subscription_expires_at.isoformat() if user.subscription_expires_at else None,
            "watering_streak": user.watering_streak,
            "created_at": user.created_at.isoformat()
        }
        
        return make_success_response(profile_data, "Perfil carregado com sucesso.")

    except NotFound as e:
        return make_error_response(str(e), "NOT_FOUND", 404)
    except Exception as e:
        current_app.logger.error(f"Erro em GET /profile/me: {e}")
        return make_error_response("Erro interno ao buscar perfil.", "INTERNAL_SERVER_ERROR", 500)


@profile_bp.route('/me', methods=['PUT'])
@jwt_required()
def update_my_profile():
    """
    Atualiza os dados de perfil do usuário logado.
    O Flutter enviará apenas os campos que mudaram.
    """
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)

        if not user:
            raise NotFound("Usuário não encontrado.")
            
        data = request.get_json()
        if not data:
            raise BadRequest("Nenhum dado fornecido.")

        # Atualiza os campos de forma condicional (só se eles existirem no JSON)
        # Campos de segurança (email, senha) e assinatura NÃO são atualizados aqui.
        
        if 'bio' in data:
            user.bio = data['bio']
            
        if 'country' in data:
            user.country = data['country']
            
        if 'state' in data:
            user.state = data['state']
        
        # (O upload de 'profile_picture_url' seria um endpoint separado,
        # mas podemos permitir a atualização da URL se ela for enviada)
        if 'profile_picture_url' in data:
             user.profile_picture_url = data['profile_picture_url']

        db.session.commit()
        
        # Retorna os dados atualizados
        updated_data = {
            "bio": user.bio,
            "country": user.country,
            "state": user.state,
            "profile_picture_url": user.profile_picture_url
        }

        return make_success_response(updated_data, "Perfil atualizado com sucesso.")

    except NotFound as e:
        return make_error_response(str(e), "NOT_FOUND", 404)
    except BadRequest as e:
        return make_error_response(str(e), "BAD_REQUEST", 400)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro em PUT /profile/me: {e}")
        return make_error_response("Erro interno ao atualizar perfil.", "INTERNAL_SERVER_ERROR", 500)