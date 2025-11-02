"""
Módulo pai administrador do firebasecli que
chama as queues de acordo com as suas funções.
"""

from app import create_app
from celery import Celery
import os
import firebase_admin
from firebase_admin import credentials

cred = credentials.Certificate(os.getenv('GOOGLE_APPLICATION_CREDENTIALS'))
firebase_admin.initialize_app(cred)

def make_celery(app):
    """
    Função 'factory' para criar e configurar a instância do Celery.
    """

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