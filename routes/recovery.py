"""
Student Portal Route – Secure Google OAuth Login.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from extensions import db, limiter, oauth
from models import User

recovery_bp = Blueprint("recovery", __name__, url_prefix="/recovery")


@recovery_bp.route("/", methods=["GET"])
@limiter.limit("10 per minute")
def portal():
    """Step 1: Student Portal landing page with 'Sign In with Google' button."""
    # If the user is already authenticated in the portal
    if "student_id" in session:
        return redirect(url_for("recovery.profile"))
    return render_template("recovery/request.html")


@recovery_bp.route("/login", methods=["GET", "POST"])
def login():
    """Trigger the Google OAuth redirect."""
    redirect_uri = url_for("recovery.callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@recovery_bp.route("/callback")
def callback():
    """Handle the Google OAuth callback."""
    try:
        # Get the token to exchange for profile info
        token = oauth.google.authorize_access_token()
        user_info = token.get("userinfo")
        
        if not user_info or not user_info.get("email"):
            flash("Authentication failed. Email not provided by Google.", "danger")
            return redirect(url_for("recovery.portal"))
            
        email = user_info.get("email")
        
        # Enforce Domain Restriction
        if not email.endswith("@itbhu.ac.in"):
            flash("Unauthorized domain. Please use your official @itbhu.ac.in email address.", "danger")
            return redirect(url_for("recovery.portal"))
            
        # Match email to database
        user = User.query.filter_by(email=email).first()
        
        if not user:
            flash("No account exists for this email address. Please contact administration.", "danger")
            return redirect(url_for("recovery.portal"))
            
        if user.effective_status != "active":
            flash("This ID is inactive or expired. Contact administration.", "warning")
            return redirect(url_for("recovery.portal"))
            
        # Authenticate successfully via session
        session["student_id"] = user.id
        flash(f"Welcome back, {user.name}!", "success")
        return redirect(url_for("recovery.profile"))

    except Exception as e:
        current_app.logger.error(f"Google OAuth Error: {e}")
        flash("An error occurred during authentication. Please try again.", "danger")
        return redirect(url_for("recovery.portal"))


@recovery_bp.route("/profile")
def profile():
    """Student Profile Dashboard - accessible only after successful Google login."""
    student_id = session.get("student_id")
    if not student_id:
        flash("Please sign in.", "warning")
        return redirect(url_for("recovery.portal"))
        
    user = db.session.get(User, student_id)
    if not user:
        session.pop("student_id", None)
        return redirect(url_for("recovery.portal"))
        
    # Reuse the same ID verification template but pass a flag indicating it's a profile view
    return render_template(
        "verify/result.html",
        user=user,
        status="active",
        blocked=False,
        anomaly=None,
        photo_scans_remaining=getattr(user, "photo_warning_scans", 0),  # Example, adjust if needed
        college=current_app.config["COLLEGE_NAME"],
        pending_photo=None, # Update Requests could be shown here if needed
        pending_hostel=None,
        is_profile_preview=True
    )


@recovery_bp.route("/logout")
def logout():
    """Log the student out of the portal."""
    session.pop("student_id", None)
    flash("You have been signed out.", "info")
    return redirect(url_for("recovery.portal"))
