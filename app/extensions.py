from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Instancia as extensões sem associá-las a nenhuma aplicação ainda.
# Elas estão "desligadas" até que a factory as conecte, para evitar
# problemas de importação circular.
db = SQLAlchemy()
migrate = Migrate()