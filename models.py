"""
SQLAlchemy database models.
"""
from datetime import datetime, date, timedelta
from flask_login import UserMixin
from extensions import db





class Admin(UserMixin, db.Model):
    """Admin user for the management panel (Superadmin)."""
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_superadmin(self):
        return True  # All admins are now superadmins

    def __repr__(self):
        return f"<Admin {self.username}>"

class Scanner(db.Model):
    """Scanner user dedicated specifically for scanning QR codes at entry points."""
    __tablename__ = "scanners"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    plain_password = db.Column(db.String(255), nullable=True)
    location_name = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_scanner(self):
        return True

    def __repr__(self):
        return f"<Scanner {self.location_name}>"


class User(db.Model):
    """Student / ID card holder."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    student_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    course = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=True)
    dob = db.Column(db.Date, nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    aadhar_number = db.Column(db.String(12), nullable=True)  # 12-digit Aadhar, not shown on ID card
    father_name = db.Column(db.String(120), nullable=True)
    contact_number = db.Column(db.String(15), nullable=True)
    blood_group = db.Column(db.String(5), nullable=True)  # e.g. A+, B-, O+, AB+
    hostel_name = db.Column(db.String(100), nullable=True)
    home_address = db.Column(db.Text, nullable=True)
    photo = db.Column(db.String(255), nullable=True)  # filename
    photo_updated_at = db.Column(db.DateTime, nullable=True)  # when photo was last set
    photo_warning_scans = db.Column(db.Integer, default=0, nullable=False, server_default="0")  # countdown scans shown
    status = db.Column(db.String(10), nullable=False, default="active")  # active / inactive / expired
    expiry_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    token = db.relationship("Token", backref="user", uselist=False, cascade="all, delete-orphan")
    scan_logs = db.relationship("ScanLog", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    update_requests = db.relationship("UpdateRequest", backref="user", lazy="dynamic", cascade="all, delete-orphan")

    @property
    def is_expired(self):
        """Check if the ID card has expired."""
        return date.today() > self.expiry_date

    @property
    def effective_status(self):
        """Return the effective status, accounting for expiry."""
        if self.status == "active" and self.is_expired:
            return "expired"
        return self.status

    @property
    def photo_needs_update(self):
        """True if photo is missing OR older than 6 months."""
        if not self.photo:
            return True
        if self.photo_updated_at is None:
            return True  # legacy record with unknown upload date — treat as stale
        return datetime.utcnow() - self.photo_updated_at > timedelta(days=180)

    def __repr__(self):
        return f"<User {self.student_id} – {self.name}>"


class Token(db.Model):
    """Secure token linked to a user, embedded in QR codes."""
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
    """Audit log for every QR scan / verification attempt."""
    __tablename__ = "scan_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    token_used = db.Column(db.String(64), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)
    result = db.Column(db.String(20), nullable=False)  # success / invalid / expired / rate_limited
    location = db.Column(db.String(120), nullable=True)  # scan location, e.g. "Library", "External"

    def __repr__(self):
        return f"<ScanLog {self.result} @ {self.timestamp}>"


class UpdateRequest(db.Model):
    """Student-submitted request to update a profile field (photo or hostel name).
    Changes are NOT applied directly — an admin must approve them.
    """
    __tablename__ = "update_requests"

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    request_type = db.Column(db.String(20), nullable=False)          # "photo" | "hostel"
    new_value   = db.Column(db.String(255), nullable=True)           # pending photo filename OR new hostel name
    status      = db.Column(db.String(20), default="pending", nullable=False)  # pending | approved | rejected
    rejection_note = db.Column(db.String(255), nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<UpdateRequest {self.request_type} user={self.user_id} [{self.status}]>"
