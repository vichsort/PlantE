"""
Define o catálogo central de todas as conquistas (badges)
disponíveis no sistema.
"""

from app.models.database import User, UserAchievement, db
from flask import current_app

# Usamos os IDs (chaves) como o ID da conquista no banco.
# Adicionei um 'icon_name' que o Flutter pode usar para exibir
# um ícone do Material Icons, por exemplo.
ACHIEVEMENT_DEFINITIONS = {
    # Assinatura
    "premium_user": {
        "name": "Apoiador Premium",
        "description": "Obrigado por apoiar o desenvolvimento do Plante!",
        "icon_name": "workspace_premium"
    },
    "premium_3_months": {
        "name": "Apoiador Bronze",
        "description": "Assinante premium por 3 meses consecutivos.",
        "icon_name": "military_tech"
    },
    "premium_6_months": {
        "name": "Apoiador Prata",
        "description": "Assinante premium por 6 meses consecutivos.",
        "icon_name": "military_tech"
    },
    "premium_1_year": {
        "name": "Apoiador Ouro",
        "description": "Assinante premium por 1 ano consecutivo. Você é incrível!",
        "icon_name": "military_tech"
    },
    
    # Tempo de app
    "user_3_months": {
        "name": "Jardineiro Dedicado",
        "description": "3 meses desde a sua primeira planta.",
        "icon_name": "calendar_month"
    },
    "user_6_months": {
        "name": "Botânico Experiente",
        "description": "6 meses cuidando do seu jardim virtual.",
        "icon_name": "calendar_month"
    },
    "user_1_year": {
        "name": "Aniversário Plante!",
        "description": "Parabéns pelo seu primeiro ano com a gente!",
        "icon_name": "cake"
    },

    # Streak de rega
    "streak_1_month": {
        "name": "Mão Verde",
        "description": "Manteve seus lembretes de rega em dia por 30 dias.",
        "icon_name": "water_drop"
    },
    "streak_3_months": {
        "name": "Mestre da Rega",
        "description": "Manteve seus lembretes de rega em dia por 90 dias.",
        "icon_name": "water_drop"
    },
    "streak_6_months": {
        "name": "Guardião do Oásis",
        "description": "Manteve seus lembretes de rega em dia por 6 meses.",
        "icon_name": "local_florist"
    },
    "streak_1_year": {
        "name": "Lenda da Hidratação",
        "description": "Manteve seus lembretes de rega em dia por 1 ano!",
        "icon_name": "spa"
    },
    
    # Identificacoes
    "first_plant": {
        "name": "Primeira Folha",
        "description": "Identificou sua primeira planta.",
        "icon_name": "psychology_alt"
    },
    "ten_plants": {
        "name": "Colecionador",
        "description": "Identificou 10 plantas diferentes.",
        "icon_name": "yard"
    },
    "first_deep_analysis": {
        "name": "Cientista de Plantas",
        "description": "Realizou sua primeira análise profunda com IA.",
        "icon_name": "auto_awesome"
    }
}


def get_achievement(achievement_id: str) -> dict | None:
    """Função auxiliar para buscar a definição de uma conquista pelo ID."""
    return ACHIEVEMENT_DEFINITIONS.get(achievement_id)

def grant_achievement_if_not_exists(user: User, achievement_id: str) -> bool:
    """
    Verifica se o usuário já possui a conquista e, se não, a concede.
    Adiciona ao db.session, mas NÃO FAZ COMMIT.
    Retorna True se a conquista foi recém-adicionada, False caso contrário.
    
    Importante: O chamador é responsável por fazer db.session.commit()
    """
    
    # Verifica se a conquista já existe (no DB ou na sessão atual)
    exists = db.session.query(UserAchievement.query.filter_by(
        user_id=user.id, 
        achievement_id=achievement_id
    ).exists()).scalar()
    
    if exists:
        return False # Usuário já possui esta conquista

    if achievement_id not in ACHIEVEMENT_DEFINITIONS:
         current_app.logger.warning(f"Tentativa de conceder conquista inválida: {achievement_id} para usuário {user.id}")
         return False

    # Concede a nova conquista
    current_app.logger.info(f"CONQUISTA CONCEDIDA: {user.id} -> {achievement_id}")
    new_badge = UserAchievement(user_id=user.id, achievement_id=achievement_id)
    db.session.add(new_badge)
    
    return True