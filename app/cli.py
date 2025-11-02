"""
Registro de todos os comandos do terminal que podem ser
acessados usando o cmd/pws. 
"""

import click
from flask import current_app
from app.extensions import db
from app.models.database import Achievement
from app.utils.achievement_utils import ACHIEVEMENT_DEFINITIONS
import redis

def register_commands(app):
    """Registra os comandos CLI customizados na aplicação Flask."""

    @app.cli.command("seed-achievements")
    def seed_achievements_command():
        """
        Popula a tabela 'achievements' com as definições padrão
        do arquivo achievements_utils.py.
        """
        click.echo("🌱 Iniciando o seed de conquistas no banco de dados...")
        
        try:
            added_count = 0
            for key, data in ACHIEVEMENT_DEFINITIONS.items():
                # Verifica se a conquista com este ID (chave) já existe
                exists = db.session.get(Achievement, key)
                
                if not exists:
                    # Se não existe, cria o novo objeto Achievement
                    new_achievement = Achievement(
                        id=key,
                        name=data['name'],
                        description=data['description'],
                        icon_name=data['icon_name']
                    )
                    db.session.add(new_achievement)
                    added_count += 1
                    click.echo(f"  + Adicionando: {key} ({data['name']})")
                else:
                    click.echo(f"  = Ignorando (já existe): {key}")
            
            if added_count > 0:
                db.session.commit()
                click.secho(f"\n✅ Sucesso! {added_count} novas conquistas foram adicionadas.", fg='green')
            else:
                click.secho("\n✨ Banco de dados de conquistas já estava atualizado.", fg='cyan')

        except Exception as e:
            db.session.rollback()
            click.secho(f"\n❌ Erro ao fazer o seed: {e}", fg='red')
        finally:
            db.session.remove()


    @app.cli.command("test-redis")
    def test_redis_connection():
        """
        Envia um comando 'PING' para o Redis para testar a conexão.
        """
        click.echo("⚡ Tentando se conectar ao Redis...")
        try:
            # Acessa o cliente Redis que foi anexado ao 'app' no __init__.py
            client = current_app.redis_client 
            
            resposta = client.ping()
            
            if resposta:
                click.secho(f"\n✅ Conexão bem-sucedida!", fg='green', bold=True)
                click.echo(f"   - Resposta do servidor: {resposta}")
            else:
                click.secho("\n❌ Conexão falhou (mas sem erro). Resposta inesperada.", fg='red')

        except redis.exceptions.AuthenticationError:
            click.secho("\n❌ ERRO DE AUTENTICAÇÃO!", fg='red', bold=True)
            click.echo("   - Verifique sua REDIS_PASSWORD no arquivo .env.")
        except redis.exceptions.ConnectionError as e:
            click.secho("\n❌ ERRO DE CONEXÃO!", fg='red', bold=True)
            click.echo("   - Verifique seu REDIS_ENDPOINT e REDIS_PORT no .env.")
            click.echo("   - Se estiverem certos, a rede pode estar bloqueando a porta.")
            click.echo(f"   - Detalhe: {e}")
        except Exception as e:
            click.secho(f"\n❌ Um erro inesperado ocorreu: {e}", fg='red', bold=True)