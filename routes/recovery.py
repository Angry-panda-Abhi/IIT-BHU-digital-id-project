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
        
    from services.token_service import get_active_token
    from services.qr_service import generate_qr_base64
    token_obj = get_active_token(user.id)
    
    # Check for pending update requests
    from models import UpdateRequest
    pending_photo = UpdateRequest.query.filter_by(user_id=user.id, request_type='photo', status='pending').first()
    pending_hostel = UpdateRequest.query.filter_by(user_id=user.id, request_type='hostel', status='pending').first()

    # Check if a hard photo update block is enforced
    from routes.verify import _check_photo_update_status
    hard_block, scans_remaining = _check_photo_update_status(user)
    if hard_block:
        return render_template(
            "verify/photo_update.html",
            user=user,
            no_photo=(not user.photo),
            college=current_app.config["COLLEGE_NAME"],
            is_profile_preview=True
        )

    # Reuse the same ID verification template but pass a flag indicating it's a profile view
    return render_template(
        "verify/result.html",
        user=user,
        status=user.effective_status,
        blocked=False,
        anomaly=None,
        token=token_obj.token if token_obj else None,
        sig=token_obj.hmac_signature if token_obj else None,
        qr_data_uri=generate_qr_base64(token_obj.token, token_obj.hmac_signature) if token_obj else None,
        photo_scans_remaining=getattr(user, "photo_warning_scans", 0),
        college=current_app.config["COLLEGE_NAME"],
        pending_photo=pending_photo,
        pending_hostel=pending_hostel,
        is_profile_preview=True
    )


@recovery_bp.route("/logout")
def logout():
    """Log the student out of the portal."""
    session.pop("student_id", None)
    flash("You have been signed out.", "info")
    return redirect(url_for("recovery.portal"))


# ---------------------------------------------------------------------------
# Student Self-Service Actions
# ---------------------------------------------------------------------------

def _allowed_photo(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in current_app.config.get("ALLOWED_EXTENSIONS", {"png", "jpg", "jpeg"})

@recovery_bp.route("/update-photo", methods=["POST"])
@limiter.limit("5 per minute")
def update_photo():
    """Update profile photo directly (used during hard block)."""
    student_id = session.get("student_id")
    if not student_id:
        flash("Please sign in.", "warning")
        return redirect(url_for("recovery.portal"))
        
    user = db.session.get(User, student_id)
    if not user:
        session.pop("student_id", None)
        return redirect(url_for("recovery.portal"))

    if "photo" not in request.files or not request.files["photo"].filename:
        flash("Please select a photo to upload.", "danger")
        return redirect(url_for("recovery.profile"))

    file = request.files["photo"]
    if not _allowed_photo(file.filename):
        flash("Invalid file type. Please upload a JPG or PNG image.", "danger")
        return redirect(url_for("recovery.profile"))

    # Save the new photo
    from services.cloud_storage import upload_photo
    from datetime import datetime
    photo_result = upload_photo(file)

    user.photo = photo_result
    user.photo_updated_at = datetime.utcnow()
    user.photo_warning_scans = 0
    db.session.commit()

    flash("Profile photo updated successfully.", "success")
    return redirect(url_for("recovery.profile"))


@recovery_bp.route("/submit-request", methods=["POST"])
@limiter.limit("5 per minute")
def submit_request():
    """Submit a request for profile change (requires admin approval)."""
    student_id = session.get("student_id")
    if not student_id:
        flash("Please sign in.", "warning")
        return redirect(url_for("recovery.portal"))
        
    user = db.session.get(User, student_id)
    if not user:
        session.pop("student_id", None)
        return redirect(url_for("recovery.portal"))

    from models import UpdateRequest
    from datetime import datetime
    req_type = request.form.get("request_type", "")

    if req_type == "photo":
        if "photo" not in request.files or not request.files["photo"].filename:
            flash("Please select a photo to upload.", "danger")
            return redirect(url_for("recovery.profile"))

        file = request.files["photo"]
        if not _allowed_photo(file.filename):
            flash("Invalid file type. Please upload a JPG or PNG photo.", "danger")
            return redirect(url_for("recovery.profile"))

        from services.cloud_storage import upload_photo
        unique_name = upload_photo(file)

        existing = UpdateRequest.query.filter_by(user_id=user.id, request_type="photo", status="pending").first()
        if existing:
            existing.new_value  = unique_name
            existing.created_at = datetime.utcnow()
        else:
            db.session.add(UpdateRequest(user_id=user.id, request_type="photo", new_value=unique_name))
        db.session.commit()

        flash("📷 Photo update request submitted! Admin will review it shortly.", "success")

    elif req_type == "hostel":
        new_hostel = request.form.get("new_value", "").strip()
        if not new_hostel:
            flash("Please enter a new hostel name.", "danger")
            return redirect(url_for("recovery.profile"))

        existing = UpdateRequest.query.filter_by(user_id=user.id, request_type="hostel", status="pending").first()
        if existing:
            existing.new_value  = new_hostel
            existing.created_at = datetime.utcnow()
        else:
            db.session.add(UpdateRequest(user_id=user.id, request_type="hostel", new_value=new_hostel))
        db.session.commit()

        flash("🏠 Hostel name change request submitted! Admin will review it shortly.", "success")

    else:
        flash("Invalid request type.", "danger")

    return redirect(url_for("recovery.profile"))
