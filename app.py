import os
import logging
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, render_template, url_for
from config import Config
from extensions import db, login_manager, limiter, mail, csrf


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)


    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(os.path.join(app.instance_path), exist_ok=True)


    from extensions import db, login_manager, limiter, mail, csrf, oauth
    
    db.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    oauth.init_app(app)


    oauth.register(
        name='google',
        client_id=app.config.get("GOOGLE_CLIENT_ID"),
        client_secret=app.config.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )


    if app.config.get("CLOUDINARY_URL"):
        import cloudinary
        cloudinary.config(cloudinary_url=app.config["CLOUDINARY_URL"])
        app.logger.info("☁️ Cloudinary configured for photo storage.")



    from routes.admin import admin_bp
    from routes.scanner import scanner_bp
    from routes.verify import verify_bp
    from routes.recovery import recovery_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(scanner_bp)
    app.register_blueprint(verify_bp)
    app.register_blueprint(recovery_bp)


    @app.route("/")
    def index():
        from flask_login import logout_user, current_user
        from flask import session
        if current_user.is_authenticated:
            logout_user()
        session.pop("scanner_auth_id", None)
        return render_template("landing.html", college=app.config["COLLEGE_NAME"])


    @app.before_request
    def load_scanner_session():
        from flask import session, g
        from models import Scanner
        
        g.active_scanner = None
        
        if "scanner_auth_id" in session:
            scanner_user = db.session.get(Scanner, session["scanner_auth_id"])
            if scanner_user and scanner_user.is_scanner:
                g.active_scanner = scanner_user

    @app.context_processor
    def inject_scanner():
        from flask import g
        return dict(active_scanner=getattr(g, 'active_scanner', None))

    @app.context_processor
    def inject_photo_helper():
        
        def photo_url(photo_value):
            if not photo_value:
                return None
            if photo_value.startswith("http"):
                return photo_value
            return url_for('static', filename='uploads/' + photo_value)
        return dict(photo_url=photo_url)

    @app.template_filter('to_ist')
    def to_ist_filter(dt):
        
        from datetime import timedelta
        if dt is None:
            return ""
        return (dt + timedelta(hours=5, minutes=30)).strftime('%d %b %Y, %I:%M:%S %p') + " IST"


    @app.after_request
    def add_cache_control(response):
        from flask import request as req
        if req.path.startswith("/admin"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def rate_limited(e):
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500


    with app.app_context():
        db.create_all()


        from sqlalchemy import text
        migrations = [
            "ALTER TABLE scanners ADD COLUMN IF NOT EXISTS scanner_type VARCHAR(20) NOT NULL DEFAULT 'general'",
            "ALTER TABLE scanners ADD COLUMN IF NOT EXISTS assigned_hostel VARCHAR(120)",
            "ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS is_cross_hostel BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE scan_logs ADD COLUMN IF NOT EXISTS cross_hostel_reason VARCHAR(255)",
            "ALTER TABLE update_requests ADD COLUMN IF NOT EXISTS reporter_info VARCHAR(120)"
        ]
        for sql in migrations:
            try:

                db.session.execute(text(sql))
                db.session.commit()
            except Exception as e:
                db.session.rollback()

                if "already exists" not in str(e).lower() and "duplicate column" not in str(e).lower():
                    app.logger.warning(f"Migration notice: {str(e)[:100]}")
        
        from models import Admin
        if not Admin.query.first():
            import bcrypt
            print("🌱 Seeding default admin account...")

            password = os.environ.get("INITIAL_ADMIN_PASSWORD", "SecureAdmin@2026")
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            admin = Admin(username="admin", password_hash=hashed)
            db.session.add(admin)
            db.session.commit()
            print(f"✅ Default admin 'admin' created. Password: {'[REDACTED]' if os.environ.get('INITIAL_ADMIN_PASSWORD') else password}")



    if not app.debug:
        logging.basicConfig(level=logging.INFO)

    return app



app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

