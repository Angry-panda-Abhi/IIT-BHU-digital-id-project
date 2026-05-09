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





def _get_scan_location():
    
    source = request.args.get('source')

    if source == 'admin':
        return "Admin Node"

    from flask import g
    active_scanner = getattr(g, 'active_scanner', None)
    if source == 'scanner' and active_scanner and getattr(active_scanner, "location_name", None):
        return active_scanner.location_name

    return "External"


def _check_photo_update_status(user):
    

    if not user.photo:
        return True, 0


    if not user.photo_needs_update:


        if user.photo_warning_scans != 0:
            user.photo_warning_scans = 0
            db.session.commit()
        return False, 0


    warning_count = user.photo_warning_scans or 0
    if warning_count >= 3:
        return True, 0


    scans_remaining = 3 - warning_count
    user.photo_warning_scans = warning_count + 1
    db.session.commit()
    return False, scans_remaining


def _allowed_photo(filename):
    allowed = current_app.config.get("ALLOWED_EXTENSIONS", {"png", "jpg", "jpeg"})
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed






@verify_bp.route("/verify")
@limiter.limit("10 per minute")
def verify():
    token_value = request.args.get("token", "")
    signature = request.args.get("sig", "")
    location = _get_scan_location()
    is_external = location == "External"


    token_obj, error = validate_token(token_value, signature)

    if error:
        if location != "External":
            log_scan(user_id=None, token_used=token_value[:64], result="invalid", location=location)
        return render_template("verify/invalid.html", reason=error), 200

    user = token_obj.user


    effective = user.effective_status
    if effective in ("expired", "inactive"):
        if location != "External":
            log_scan(user_id=user.id, token_used=token_value, result="expired", location=location)
        return render_template("verify/invalid.html", reason="not_found"), 200


    from flask import g
    active_scanner = getattr(g, 'active_scanner', None)
    is_cross_hostel = False
    
    if active_scanner and active_scanner.scanner_type == 'hostel':
        student_hostel = (user.hostel_name or "").lower().strip()
        assigned_hostel = (active_scanner.assigned_hostel or "").lower().strip()
        if student_hostel != assigned_hostel:
            is_cross_hostel = True


    scan_log = None
    if location != "External":
        scan_log = log_scan(user_id=user.id, token_used=token_value, result="success", location=location)
    
        if is_cross_hostel and scan_log:
            scan_log.is_cross_hostel = True
            db.session.commit()


    hard_block, scans_remaining = _check_photo_update_status(user)

    if hard_block:

        return render_template(
            "verify/photo_update.html",
            user=user,
            token=token_value,
            sig=signature,
            no_photo=(not user.photo),
            college=current_app.config["COLLEGE_NAME"],
            is_profile_preview=False
        )


    from models import ScanLog
    previous_scan = ScanLog.query.filter_by(user_id=user.id, result="success")\
        .filter(ScanLog.location != "External")\
        .order_by(ScanLog.timestamp.desc()).offset(1).first()


    anomaly = detect_anomaly(token_value)

    pending_photo = UpdateRequest.query.filter_by(user_id=user.id, request_type="photo", status="pending").first()
    pending_hostel = UpdateRequest.query.filter_by(user_id=user.id, request_type="hostel", status="pending").first()


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
        is_cross_hostel=is_cross_hostel,
        scan_log=scan_log,
        active_scanner=active_scanner,
        previous_scan=previous_scan,
        is_external=is_external,
    )


