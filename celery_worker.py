from app import create_app
from celery import Celery

def make_celery(app):
    """
    Função 'factory' para criar e configurar a instância do Celery.
    """
    # 1. Configura o Celery com o Broker e Backend do config.py do Flask
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config)

    # Ele garante que toda tarefa Celery rode dentro de um "contexto"
    # do Flask, para que as tarefas possam usar 'db.session', 'current_app', etc.
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

flask_app = create_app()

celery = make_celery(flask_app)