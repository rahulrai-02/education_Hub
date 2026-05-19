from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ==========================================
# USER MODEL (Contains all Gen Alpha Form Fields)
# ==========================================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # Core Auth & Identifiers
    username = db.Column(db.String(150), unique=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), default='student')
    phone = db.Column(db.String(20))
    aadhar = db.Column(db.String(12))
    
    # Personal Info
    fullname = db.Column(db.String(150))
    gender = db.Column(db.String(20))
    dob = db.Column(db.String(50)) 
    
    # Academic Info
    school = db.Column(db.String(200))
    class_grade = db.Column(db.String(50))
    stream = db.Column(db.String(100))
    
    # Location Info
    address = db.Column(db.String(250))
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    district = db.Column(db.String(100))

    # --- THIS FIXES THE VS CODE LINTER ERRORS ---
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)

    # Password Hashing Functions
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# ==========================================
# ACTION LOG MODEL (For Teacher/Admin Tracking)
# ==========================================
class ActionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship tying the log back to the User who performed it
    user = db.relationship('User', backref=db.backref('logs', lazy=True))

    # --- THIS FIXES THE VS CODE LINTER ERRORS ---
    def __init__(self, **kwargs):
        super(ActionLog, self).__init__(**kwargs)