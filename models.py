from datetime import datetime, date, timedelta
from flask_login import UserMixin
from extensions import db





class Admin(UserMixin, db.Model):
    
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_superadmin(self):
        return True

    def __repr__(self):
        return f"<Admin {self.username}>"

class Scanner(db.Model):
    
    __tablename__ = "scanners"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    plain_password = db.Column(db.String(255), nullable=True)
    location_name = db.Column(db.String(120), nullable=True)
    scanner_type = db.Column(db.String(20), nullable=False, default="general", server_default="general")
    assigned_hostel = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_scanner(self):
        return True

    def __repr__(self):
        return f"<Scanner {self.location_name}>"


class User(db.Model):
    
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    student_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    course = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=True)
    dob = db.Column(db.Date, nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    aadhar_number = db.Column(db.String(12), nullable=True)
    father_name = db.Column(db.String(120), nullable=True)
    contact_number = db.Column(db.String(15), nullable=True)
    blood_group = db.Column(db.String(5), nullable=True)
    hostel_name = db.Column(db.String(100), nullable=True)
    home_address = db.Column(db.Text, nullable=True)
    photo = db.Column(db.String(255), nullable=True)
    photo_updated_at = db.Column(db.DateTime, nullable=True)
    photo_warning_scans = db.Column(db.Integer, default=0, nullable=False, server_default="0")
    status = db.Column(db.String(10), nullable=False, default="active")
    expiry_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


    token = db.relationship("Token", backref="user", uselist=False, cascade="all, delete-orphan")
    scan_logs = db.relationship("ScanLog", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    update_requests = db.relationship("UpdateRequest", backref="user", lazy="dynamic", cascade="all, delete-orphan")

    @property
    def is_expired(self):
        
        return date.today() > self.expiry_date

    @property
    def effective_status(self):
        
        if self.status == "active" and self.is_expired:
            return "expired"
        return self.status

    @property
    def photo_needs_update(self):
        
        if not self.photo:
            return True
        if self.photo_updated_at is None:
            return True
        return datetime.utcnow() - self.photo_updated_at > timedelta(days=180)

    def __repr__(self):
        return f"<User {self.student_id} – {self.name}>"


class Token(db.Model):
    
    __tablename__ = "tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    hmac_signature = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_revoked = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<Token {self.token[:8]}… for user {self.user_id}>"


class ScanLog(db.Model):
    
    __tablename__ = "scan_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    token_used = db.Column(db.String(64), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)
    result = db.Column(db.String(20), nullable=False)
    location = db.Column(db.String(120), nullable=True)
    is_cross_hostel = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    cross_hostel_reason = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f"<ScanLog {self.result} @ {self.timestamp}>"


class UpdateRequest(db.Model):
    
    __tablename__ = "update_requests"

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    request_type = db.Column(db.String(20), nullable=False)
    new_value   = db.Column(db.String(255), nullable=True)
    status      = db.Column(db.String(20), default="pending", nullable=False)
    rejection_note = db.Column(db.String(255), nullable=True)
    reporter_info = db.Column(db.String(120), nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)

class RegistrationRequest(db.Model):
    
    __tablename__ = "registration_requests"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    student_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    course = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=True)
    dob = db.Column(db.Date, nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    aadhar_number = db.Column(db.String(12), nullable=True)
    father_name = db.Column(db.String(120), nullable=True)
    contact_number = db.Column(db.String(15), nullable=True)
    blood_group = db.Column(db.String(5), nullable=True)
    hostel_name = db.Column(db.String(100), nullable=True)
    home_address = db.Column(db.Text, nullable=True)
    photo = db.Column(db.String(255), nullable=True)
    
    status = db.Column(db.String(20), default="pending", nullable=False)
    rejection_note = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<RegistrationRequest {self.student_id} [{self.status}]>"
