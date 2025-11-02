"""
Blueprints/rotas relacionados à verificação
de segurança do usuário. São:
(prefixo /api/v1/auth/)
- /register -> cria conta
- /login -> entra na conta
- /fc_token -> registra token do push
- /upgrade-to-premium -> (TEMPORARIO) deixa a conta premium
- /revert-to-free -> (TEMPORARIO) deixa a conta free
"""

from flask import Blueprint, request
from app.models.database import User
from app.extensions import db
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.exceptions import BadRequest, Unauthorized, Conflict, NotFound
from app.utils.response_utils import make_success_response, make_error_response
from app.utils.achievement_utils import grant_achievement_if_not_exists
from datetime import datetime, timedelta

auth_bp = Blueprint('auth_bp', __name__, url_prefix='/api/v1/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    """Endpoint para registrar um novo usuário (começa como 'free' por padrão)."""
    try:
        data = request.get_json()
        if not data or not data.get('email') or not data.get('password'):
            raise BadRequest("Email e senha são obrigatórios.")

        email = data['email']
        password = data['password']

        if User.query.filter_by(email=email).first():
            raise Conflict("Este email já está em uso.")

        new_user = User(email=email)
        new_user.set_password(password)
        # subscription_status usará o 'default' do modelo (free)
        
        db.session.add(new_user)
        db.session.commit()

        return make_success_response(
            data={"user_id": str(new_user.id)}, # Retorna o ID como string
            message="Usuário registrado com sucesso.",
            status_code=201
        )
    except BadRequest as e:
        db.session.rollback() # Garante rollback em caso de erro
        return make_error_response(str(e), "BAD_REQUEST", 400)
    except Conflict as e:
        db.session.rollback()
        return make_error_response(str(e), "EMAIL_IN_USE", 409)
    except Exception as e:
        db.session.rollback()
        return make_error_response("Ocorreu um erro interno durante o registro.", "INTERNAL_SERVER_ERROR", 500)


@auth_bp.route('/login', methods=['POST'])
def login():
    """Endpoint para login e obtenção de token."""
    try:
        data = request.get_json()
        if not data or not data.get('email') or not data.get('password'):
            raise BadRequest("Email e senha são obrigatórios.")

        email = data['email']
        password = data['password']

        user = User.query.filter_by(email=email).first()

        if user is None or not user.check_password(password):
            raise Unauthorized("Credenciais inválidas.")

        access_token = create_access_token(identity=str(user.id))

        return make_success_response(
            data={"token": access_token, "subscription_status": user.subscription_status},
            message="Login bem-sucedido."
        )
    except BadRequest as e:
        return make_error_response(str(e), "BAD_REQUEST", 400)
    except Unauthorized as e:
        return make_error_response(str(e), "INVALID_CREDENTIALS", 401)
    except Exception as e:
        return make_error_response("Ocorreu um erro interno durante o login.", "INTERNAL_SERVER_ERROR", 500)


@auth_bp.route('/fcm-token', methods=['POST'])
@jwt_required()
def update_fcm_token():
    """
    Atualiza o token FCM (push notification) do usuário logado.
    """
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        fcm_token = data.get('fcm_token')

        if not fcm_token:
            raise BadRequest("O 'fcm_token' é obrigatório no corpo da requisição.")

        user = User.query.get(current_user_id)
        if not user:
            raise NotFound("Usuário associado ao token não encontrado.") 

        user.fcm_token = fcm_token
        user.fcm_token_updated_at = datetime.utcnow() # Atualiza a data
        db.session.commit()

        return make_success_response(
            data=None,
            message="Token do dispositivo atualizado com sucesso."
        )
    except BadRequest as e:
        db.session.rollback()
        return make_error_response(str(e), "BAD_REQUEST", 400)
    except NotFound as e:
        db.session.rollback()
        return make_error_response(str(e), "NOT_FOUND", 404)
    except Exception as e:
        db.session.rollback()
        return make_error_response(f"Ocorreu um erro interno ao atualizar o token: {str(e)}", "INTERNAL_SERVER_ERROR", 500)


@auth_bp.route('/fcm-token', methods=['DELETE'])
@jwt_required()
def remove_fcm_token():
    """
    Remove o token FCM do usuário (usado no logout ou ao desativar notificações).
    """
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)

        if not user:
            raise NotFound("Usuário associado ao token não encontrado.")

        user.fcm_token = None
        user.fcm_token_updated_at = None # Limpa a data também
        db.session.commit()

        return make_success_response(
            data=None,
            message="Token do dispositivo desvinculado com sucesso."
        )
    except NotFound as e:
        db.session.rollback()
        return make_error_response(str(e), "NOT_FOUND", 404)
    except Exception as e:
        db.session.rollback()
        return make_error_response(f"Ocorreu um erro interno ao desvincular o token: {str(e)}", "INTERNAL_SERVER_ERROR", 500)

@auth_bp.route('/upgrade-to-premium', methods=['POST'])
@jwt_required()
def upgrade_to_premium():
    """
    (TESTE) Atualiza o usuário logado para o status 'premium' por 30 dias.
    """
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)

        if not user:
            raise NotFound("Usuário associado ao token não encontrado.")

        user.subscription_status = 'premium'
        user.subscription_expires_at = datetime.utcnow() + timedelta(days=30)
        grant_achievement_if_not_exists(user, 'premium_user')
        db.session.commit()

        return make_success_response(
            data={
                "subscription_status": user.subscription_status,
                "expires_at": user.subscription_expires_at.isoformat()
            },
            message="Usuário atualizado para Premium com sucesso."
        )
    except NotFound as e:
        db.session.rollback()
        return make_error_response(str(e), "NOT_FOUND", 404)
    except Exception as e:
        db.session.rollback()
        return make_error_response(f"Ocorreu um erro interno: {str(e)}", "INTERNAL_SERVER_ERROR", 500)


@auth_bp.route('/revert-to-free', methods=['POST'])
@jwt_required()
def revert_to_free():
    """
    (TESTE) Reverte o usuário logado para o status 'free'.
    """
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)

        if not user:
            raise NotFound("Usuário associado ao token não encontrado.")

        user.subscription_status = 'free'
        user.subscription_expires_at = None
        db.session.commit()

        return make_success_response(
            data={"subscription_status": user.subscription_status},
            message="Usuário revertido para Free com sucesso."
        )
    except NotFound as e:
        db.session.rollback()
        return make_error_response(str(e), "NOT_FOUND", 404)
    except Exception as e:
        db.session.rollback()
        return make_error_response(f"Ocorreu um erro interno: {str(e)}", "INTERNAL_SERVER_ERROR", 500)