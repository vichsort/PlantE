import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = 'users'
    
    # identificação básica
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # para as notificações push
    fcm_token = db.Column(db.Text, nullable=True)
    fcm_token_updated_at = db.Column(db.DateTime, nullable=True)

    # Relativos ao freemium
    subscription_status = db.Column(
        db.String(30), 
        nullable=False, 
        default='free',  # Valores: 'free', 'premium', 'trial'
        server_default='free'
    )
    subscription_expires_at = db.Column(db.DateTime, nullable=True)

    # gamificação - futuro
    watering_streak = db.Column(db.Integer, default=0, nullable=False)

    # profile
    bio = db.Column(db.Text, nullable=True)
    profile_picture_url = db.Column(db.String(512), nullable=True) 
    country = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(100), nullable=True)
    
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
    health_cache = db.Column(JSONB, nullable=True)

class UserPlant(db.Model):
    __tablename__ = 'user_garden'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nickname = db.Column(db.String(100))
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_watered = db.Column(db.DateTime)
    care_notes = db.Column(db.Text)
    tracked_watering = db.Column(db.Boolean, default=False, nullable=False)
    primary_image_url = db.Column(db.String(512), nullable=True)
    
    # Chaves Estrangeiras que conectam tudo
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    plant_entity_id = db.Column(db.String(50), db.ForeignKey('plant_guide.entity_id'), nullable=False)

    # Relacionamentos
    owner = db.relationship('User', back_populates='garden')
    plant_info = db.relationship('PlantGuide')

class Achievement(db.Model):
    __tablename__ = 'achievements'
    
    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    icon_name = db.Column(db.String(50), nullable=True)
    
    # Relacionamento (quantos usuários ganharam esta conquista)
    users = db.relationship('UserAchievement', back_populates='achievement')

class UserAchievement(db.Model):
    __tablename__ = 'user_achievements'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Chaves Estrangeiras
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False, index=True)
    achievement_id = db.Column(db.String(50), db.ForeignKey('achievements.id'), nullable=False, index=True)
    
    # Relacionamentos de volta
    user = db.relationship('User', back_populates='achievements')
    achievement = db.relationship('Achievement', back_populates='users')
    
    # Garante que um usuário só possa ganhar cada conquista uma vez
    __table_args__ = (db.UniqueConstraint('user_id', 'achievement_id', name='_user_achievement_uc'),)