"""
Shared Flask extension instances.
Initialized here to avoid circular imports; attached to the app in app.py.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail

db = SQLAlchemy()

login_manager = LoginManager()
login_manager.login_view = "admin.login"
login_manager.login_message_category = "warning"

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
)

mail = Mail()
