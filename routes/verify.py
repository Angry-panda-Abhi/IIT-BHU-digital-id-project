"""
Verification route – the public endpoint scanned via QR code.
"""
import os
import time
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, current_app
from flask_login import current_user
from werkzeug.utils import secure_filename

from extensions import db, limiter
from models import User, UpdateRequest
from services.token_service import validate_token
from services.security_service import log_scan, detect_anomaly

verify_bp = Blueprint("verify", __name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_scan_location():
    """Return the location tag for the current scan.
    If the request comes from an authenticated scanner account, use their
    assigned location_name.  Otherwise tag the scan as 'External'.
    """
    source = request.args.get('source')

    if source == 'admin':
        return "Admin Node"

    from flask import g
    active_scanner = getattr(g, 'active_scanner', None)
    if source == 'scanner' and active_scanner and getattr(active_scanner, "location_name", None):
        return active_scanner.location_name

    return "External"


def _check_photo_update_status(user):
    """Determine whether the user's photo needs updating and how urgent it is.

    Returns:
        (hard_block: bool, scans_remaining: int)

        hard_block=True  → show the photo upload page, do NOT show student info.
        scans_remaining>0 → show student info + amber warning with countdown.
        Both False/0      → normal verification, no warning.

    Side-effect: if a warning scan is being shown, increments
    user.photo_warning_scans and commits to DB.
    """
    # No photo at all → immediate hard block (no countdown)
    if not user.photo:
        return True, 0

    # Photo exists but is it stale?
    if not user.photo_needs_update:
        # Photo is fresh — no warning needed, also reset counter in case
        # the photo was recently refreshed by admin
        if user.photo_warning_scans != 0:
            user.photo_warning_scans = 0
            db.session.commit()
        return False, 0

    # Photo is stale — check if we've exhausted all warning scans
    warning_count = user.photo_warning_scans or 0
    if warning_count >= 3:
        return True, 0  # hard block

    # Show a warning scan and tick the counter
    scans_remaining = 3 - warning_count   # will be 3, 2, or 1
    user.photo_warning_scans = warning_count + 1
    db.session.commit()
    return False, scans_remaining


def _allowed_photo(filename):
    allowed = current_app.config.get("ALLOWED_EXTENSIONS", {"png", "jpg", "jpeg"})
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


# ---------------------------------------------------------------------------
# Verify (main public QR endpoint)
# ---------------------------------------------------------------------------

@verify_bp.route("/verify")
@limiter.limit("10 per minute")
def verify():
    token_value = request.args.get("token", "")
    signature = request.args.get("sig", "")
    location = _get_scan_location()

    # --- Validate token + HMAC ---
    token_obj, error = validate_token(token_value, signature)

    if error:
        log_scan(user_id=None, token_used=token_value[:64], result="invalid", location=location)
        return render_template("verify/invalid.html", reason=error), 200

    user = token_obj.user

    # --- Check expiry & status ---
    effective = user.effective_status
    if effective in ("expired", "inactive"):
        log_scan(user_id=user.id, token_used=token_value, result="expired", location=location)
        return render_template("verify/invalid.html", reason="not_found"), 200

    # --- Log successful scan ---
    log_scan(user_id=user.id, token_used=token_value, result="success", location=location)

    # --- Photo update check ---
    hard_block, scans_remaining = _check_photo_update_status(user)

    if hard_block:
        # Student must update photo before seeing their info
        return render_template(
            "verify/photo_update.html",
            user=user,
            token=token_value,
            sig=signature,
            no_photo=(not user.photo),
            college=current_app.config["COLLEGE_NAME"],
        )

    # --- Anomaly check ---
    anomaly = detect_anomaly(token_value)

    pending_photo = UpdateRequest.query.filter_by(user_id=user.id, request_type="photo", status="pending").first()
    pending_hostel = UpdateRequest.query.filter_by(user_id=user.id, request_type="hostel", status="pending").first()

    # Generate QR data URI for display (only if student is viewing their own profile)
    from services.qr_service import generate_qr_base64
    qr_data_uri = generate_qr_base64(token_obj.token, token_obj.hmac_signature)

    return render_template(
        "verify/result.html",
        user=user,
        status="active",
        blocked=False,
        anomaly=anomaly,
        photo_scans_remaining=scans_remaining,
        token=token_value,
        sig=signature,
        college=current_app.config["COLLEGE_NAME"],
        pending_photo=pending_photo,
        pending_hostel=pending_hostel,
        qr_data_uri=qr_data_uri,
    )


# ---------------------------------------------------------------------------
# Photo Update (student self-service, token-authenticated)
# ---------------------------------------------------------------------------

@verify_bp.route("/verify/update-photo", methods=["POST"])
@limiter.limit("5 per minute")
def update_photo():
    """Allow a student to upload a new profile photo by proving their QR token.

    The token + HMAC signature are passed as hidden form fields so this
    endpoint can identify and authenticate the student without a separate
    login system. The QR code itself is never regenerated.
    """
    token_value = request.form.get("token", "")
    signature = request.form.get("sig", "")

    # Re-validate the HMAC token so we know the upload is legitimate
    token_obj, error = validate_token(token_value, signature)
    if error:
        return render_template("verify/photo_update.html",
                               upload_error="Invalid security token. Please scan your QR code again.",
                               token=token_value, sig=signature,
                               college=current_app.config["COLLEGE_NAME"]), 400

    user = token_obj.user

    # Validate file
    if "photo" not in request.files or not request.files["photo"].filename:
        return render_template(
            "verify/photo_update.html",
            user=user, token=token_value, sig=signature,
            no_photo=(not user.photo),
            upload_error="Please select a photo to upload.",
            college=current_app.config["COLLEGE_NAME"],
        )

    file = request.files["photo"]
    if not _allowed_photo(file.filename):
        return render_template(
            "verify/photo_update.html",
            user=user, token=token_value, sig=signature,
            no_photo=(not user.photo),
            upload_error="Invalid file type. Please upload a JPG or PNG image.",
            college=current_app.config["COLLEGE_NAME"],
        )

    # Save the new photo (Cloudinary or local)
    from services.cloud_storage import upload_photo
    photo_result = upload_photo(file)

    # Update the user record — reset all warning state
    user.photo = photo_result
    user.photo_updated_at = datetime.utcnow()
    user.photo_warning_scans = 0
    db.session.commit()

    # Redirect back to the verify page — will now show normal student info
    return redirect(url_for("verify.verify", token=token_value, sig=signature))


# ---------------------------------------------------------------------------
# Submit Update Request (student self-service, token-authenticated)
# ---------------------------------------------------------------------------

@verify_bp.route("/verify/submit-request", methods=["POST"])
@limiter.limit("5 per minute")
def submit_request():
    """Create a pending UpdateRequest so an admin can approve profile changes.

    Supports:
      • request_type=photo   → uploads provisional photo, admin approves/rejects
      • request_type=hostel  → stores new hostel name, admin approves/rejects

    The QR token + HMAC signature prove the student's identity.
    Nothing is applied to the user record until an admin approves.
    """
    token_value = request.form.get("token", "")
    signature   = request.form.get("sig", "")
    req_type    = request.form.get("request_type", "")

    token_obj, error = validate_token(token_value, signature)
    if error:
        return redirect(url_for("verify.verify", token=token_value, sig=signature))

    user = token_obj.user

    if req_type == "photo":
        # --- Photo update request ---
        if "photo" not in request.files or not request.files["photo"].filename:
            from flask import flash
            flash("Please select a photo to upload.", "danger")
            return redirect(url_for("verify.verify", token=token_value, sig=signature))

        file = request.files["photo"]
        if not _allowed_photo(file.filename):
            from flask import flash
            flash("Invalid file type. Please upload a JPG or PNG photo.", "danger")
            return redirect(url_for("verify.verify", token=token_value, sig=signature))

        # Save pending photo (Cloudinary or local)
        from services.cloud_storage import upload_photo
        unique_name = upload_photo(file)

        # Replace any existing pending photo request (student re-submitted)
        existing = UpdateRequest.query.filter_by(
            user_id=user.id, request_type="photo", status="pending"
        ).first()
        if existing:
            existing.new_value  = unique_name
            existing.created_at = datetime.utcnow()
        else:
            db.session.add(UpdateRequest(
                user_id=user.id, request_type="photo", new_value=unique_name
            ))
        db.session.commit()

        from flask import flash
        flash("📷 Photo update request submitted! Admin will review it shortly.", "success")

    elif req_type == "hostel":
        # --- Hostel name update request ---
        new_hostel = request.form.get("new_value", "").strip()
        if not new_hostel:
            from flask import flash
            flash("Please enter a new hostel name.", "danger")
            return redirect(url_for("verify.verify", token=token_value, sig=signature))

        existing = UpdateRequest.query.filter_by(
            user_id=user.id, request_type="hostel", status="pending"
        ).first()
        if existing:
            existing.new_value  = new_hostel
            existing.created_at = datetime.utcnow()
        else:
            db.session.add(UpdateRequest(
                user_id=user.id, request_type="hostel", new_value=new_hostel
            ))
        db.session.commit()

        from flask import flash
        flash("🏠 Hostel name change request submitted! Admin will review it shortly.", "success")

    else:
        from flask import flash
        flash("Invalid request type.", "danger")

    return redirect(url_for("verify.verify", token=token_value, sig=signature))
