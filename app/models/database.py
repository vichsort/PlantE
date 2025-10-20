import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    fcm_token = db.Column(db.Text, nullable=True)
    
    # Relacionamento: Um usuário pode ter muitas plantas em seu jardim.
    garden = db.relationship('UserPlant', back_populates='owner', lazy='dynamic', cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class PlantGuide(db.Model):
    __tablename__ = 'plant_guide'
    
    entity_id = db.Column(db.String(50), primary_key=True)
    scientific_name = db.Column(db.String(150), nullable=False)
    last_gemini_update = db.Column(db.DateTime)
    details_cache = db.Column(JSONB)
    nutritional_cache = db.Column(JSONB)

class UserPlant(db.Model):
    __tablename__ = 'user_garden'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nickname = db.Column(db.String(100))
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_watered = db.Column(db.DateTime)
    care_notes = db.Column(db.Text)
    
    # Chaves Estrangeiras que conectam tudo
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    plant_entity_id = db.Column(db.String(50), db.ForeignKey('plant_guide.entity_id'), nullable=False)

    # Relacionamentos
    owner = db.relationship('User', back_populates='garden')
    plant_info = db.relationship('PlantGuide')