"""
Flask application factory.
"""
import os
import logging
from flask import Flask, render_template
from config import Config
from extensions import db, login_manager, limiter, mail


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure directories exist
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(os.path.join(app.instance_path), exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)
    mail.init_app(app)

    # Register blueprints
    from routes.admin import admin_bp
    from routes.scanner import scanner_bp
    from routes.verify import verify_bp
    from routes.recovery import recovery_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(scanner_bp)
    app.register_blueprint(verify_bp)
    app.register_blueprint(recovery_bp)

    # Home / Landing – kills ALL active sessions (both admin + scanner)
    @app.route("/")
    def index():
        from flask_login import logout_user, current_user
        from flask import session
        if current_user.is_authenticated:
            logout_user()
        session.pop("scanner_auth_id", None)
        return render_template("landing.html", college=app.config["COLLEGE_NAME"])

    # Parallel Scanner Session Management
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

    # Prevent browser back-button from showing cached admin pages after logout
    @app.after_request
    def add_cache_control(response):
        from flask import request as req
        if req.path.startswith("/admin"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def rate_limited(e):
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    # Create tables
    with app.app_context():
        db.create_all()

    # Logging
    if not app.debug:
        logging.basicConfig(level=logging.INFO)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
