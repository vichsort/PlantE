"""
Runner de todo o sistema. Simplesmente
acessa o arquivo app/__init__.py com
as variáveis necessárias inicializadas.
"""

from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)