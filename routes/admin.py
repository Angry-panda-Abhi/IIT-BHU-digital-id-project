"""
Admin routes – authentication, student CRUD, QR management, scan logs, RBAC.
"""
import os
from datetime import date, timedelta, datetime
from functools import wraps

import bcrypt
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, send_file, current_app, abort, session, g
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename

from extensions import db, limiter, login_manager
from models import Admin, User, Token, ScanLog, Scanner, UpdateRequest
from services.token_service import generate_token, get_active_token, revoke_token
from services.qr_service import generate_qr_image, generate_qr_base64
from services.pdf_service import generate_id_card_pdf
from services.email_service import send_qr_email
from services.security_service import get_scan_stats

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ---------------------------------------------------------------------------
# Flask-Login user loader
# ---------------------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Admin, int(user_id))


@admin_bp.context_processor
def inject_pending_requests():
    """Inject the count of pending update requests into all admin templates."""
    if current_user.is_authenticated and current_user.is_superadmin:
        count = UpdateRequest.query.filter_by(status="pending").count()
        return dict(pending_requests_count=count)
    return dict(pending_requests_count=0)


# ---------------------------------------------------------------------------
# RBAC decorator – blocks scanner accounts from superadmin-only routes
# ---------------------------------------------------------------------------
def superadmin_required(f):
    """Decorator: requires the logged-in admin to have the superadmin role."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_superadmin:
            flash("Access denied. Superadmin privileges required.", "danger")
            return redirect(url_for("admin.scanner"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _allowed_file(filename):
    allowed = current_app.config["ALLOWED_EXTENSIONS"]
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


def _save_photo(file):
    """Save an uploaded photo and return a URL (Cloudinary) or filename (local)."""
    from services.cloud_storage import upload_photo
    return upload_photo(file)


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
@admin_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = Admin.query.filter_by(username=username).first()

        if admin and bcrypt.checkpw(password.encode(), admin.password_hash.encode()):
            login_user(admin)
            flash("Welcome back!", "success")
            return redirect(url_for("admin.dashboard"))

        flash("Invalid credentials.", "danger")

    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    """Main logout: Clears everything (Admin + Scanner)."""
    from flask_login import logout_user
    if current_user.is_authenticated:
        logout_user()
    session.pop("scanner_auth_id", None)
    flash("Successfully logged out of all sessions.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Dashboard (superadmin only)
# ---------------------------------------------------------------------------
@admin_bp.route("/")
@admin_bp.route("/dashboard")
@superadmin_required
def dashboard():
    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "all")

    query = User.query.filter(User.status != "inactive")
    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(User.name.ilike(like), User.student_id.ilike(like), User.email.ilike(like))
        )
    if status_filter != "all":
        query = query.filter_by(status=status_filter)

    students = query.order_by(User.created_at.desc()).all()
    stats = get_scan_stats()

    return render_template(
        "admin/dashboard.html",
        students=students,
        stats=stats,
        search=search,
        status_filter=status_filter,
    )


# ---------------------------------------------------------------------------
# Create student (superadmin only)
# ---------------------------------------------------------------------------
@admin_bp.route("/students/new", methods=["GET", "POST"])
@superadmin_required
def create_student():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        student_id = request.form.get("student_id", "").strip()
        course = request.form.get("course", "").strip()
        department = request.form.get("department", "").strip()
        aadhar_number = request.form.get("aadhar_number", "").strip().replace(" ", "")
        father_name = request.form.get("father_name", "").strip()
        contact_number = request.form.get("contact_number", "").strip()
        blood_group = request.form.get("blood_group", "").strip()
        hostel_name = request.form.get("hostel_name", "").strip()
        home_address = request.form.get("home_address", "").strip()
        email = request.form.get("email", "").strip()
        validity_years = int(current_app.config.get("ID_VALIDITY_YEARS", 1))

        # Validation
        errors = []
        if not all([name, student_id, course, department, email]):
            errors.append("All fields are required.")

        dob_str = request.form.get("dob", "")
        dob = None
        if dob_str:
            try:
                dob = date.fromisoformat(dob_str)
            except ValueError:
                errors.append("Invalid Date of Birth format.")
        if not email.lower().endswith("@itbhu.ac.in"):
            errors.append("Only @itbhu.ac.in email addresses are allowed.")
        existing_student = User.query.filter_by(student_id=student_id).first()
        if existing_student:
            if existing_student.status == "inactive":
                for log in existing_student.scan_logs.all():
                    log.user_id = None
                for req in existing_student.update_requests.all():
                    db.session.delete(req)
                if existing_student.token:
                    db.session.delete(existing_student.token)
                    existing_student.token = None
                db.session.delete(existing_student)
                db.session.commit()
            else:
                errors.append("Student ID already exists.")
                
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            if existing_email.status == "inactive":
                for log in existing_email.scan_logs.all():
                    log.user_id = None
                for req in existing_email.update_requests.all():
                    db.session.delete(req)
                if existing_email.token:
                    db.session.delete(existing_email.token)
                    existing_email.token = None
                db.session.delete(existing_email)
                db.session.commit()
            else:
                errors.append("Email already registered.")

        expiry_str = request.form.get("expiry_date", "")
        expiry_date_val = None
        if expiry_str:
            try:
                expiry_date_val = date.fromisoformat(expiry_str)
            except ValueError:
                errors.append("Invalid Expiry Date format.")
        else:
            expiry_date_val = date.today() + timedelta(days=365 * validity_years)

        photo_filename = None
        if "photo" in request.files:
            file = request.files["photo"]
            if file.filename:
                if _allowed_file(file.filename):
                    photo_filename = _save_photo(file)
                else:
                    errors.append("Invalid photo format. Use JPG or PNG.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("admin/student_form.html", mode="create")

        user = User(
            name=name,
            student_id=student_id,
            course=course,
            department=department,
            aadhar_number=aadhar_number or None,
            father_name=father_name or None,
            contact_number=contact_number or None,
            blood_group=blood_group or None,
            hostel_name=hostel_name or None,
            home_address=home_address or None,
            dob=dob,
            email=email,
            photo=photo_filename,
            photo_updated_at=datetime.utcnow() if photo_filename else None,
            photo_warning_scans=0,
            status="active",
            expiry_date=expiry_date_val,
        )
        db.session.add(user)
        db.session.commit()

        # Generate secure token + QR
        generate_token(user.id)

        flash(f"Student {name} created successfully!", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/student_form.html", mode="create")


# ---------------------------------------------------------------------------
# View Student Profile (Admin only)
# ---------------------------------------------------------------------------
@admin_bp.route("/students/<int:user_id>/profile")
@login_required
def view_profile(user_id):
    """View a student's full digital ID card profile page."""
    user = User.query.get_or_404(user_id)
    return render_template(
        "verify/result.html",
        user=user,
        status=user.effective_status,
        blocked=False,
        anomaly=None,
        photo_scans_remaining=None,
        token=None,
        sig=None,
        college=current_app.config["COLLEGE_NAME"],
        pending_photo=None,
        pending_hostel=None,
        is_profile_preview=True,
    )



# ---------------------------------------------------------------------------
# Edit student (superadmin only)
# ---------------------------------------------------------------------------
@admin_bp.route("/students/<int:user_id>/edit", methods=["GET", "POST"])
@superadmin_required
def edit_student(user_id):
    user = User.query.get_or_404(user_id)
    token = user.token

    if request.method == "POST":
        user.name = request.form.get("name", user.name).strip()
        
        new_sid = request.form.get("student_id", "").strip()
        if new_sid and new_sid != user.student_id:
            if User.query.filter_by(student_id=new_sid).first():
                flash("Student ID already exists.", "danger")
                return render_template("admin/student_form.html", mode="edit", student=user, token=token)
            user.student_id = new_sid

        user.course = request.form.get("course", user.course).strip()
        user.department = request.form.get("department", user.department or "").strip()
        aadhar_raw = request.form.get("aadhar_number", "").strip().replace(" ", "")
        user.aadhar_number = aadhar_raw or user.aadhar_number
        user.father_name = request.form.get("father_name", "").strip() or user.father_name
        user.contact_number = request.form.get("contact_number", "").strip() or user.contact_number
        user.blood_group = request.form.get("blood_group", "").strip() or user.blood_group
        user.hostel_name = request.form.get("hostel_name", "").strip() or user.hostel_name
        user.home_address = request.form.get("home_address", "").strip() or user.home_address
        
        dob_str = request.form.get("dob", "")
        if dob_str:
            try:
                user.dob = date.fromisoformat(dob_str)
            except ValueError:
                flash("Invalid Date of Birth format.", "danger")
                return render_template("admin/student_form.html", mode="edit", student=user, token=token)

        new_email = request.form.get("email", user.email).strip()
        if not new_email.lower().endswith("@itbhu.ac.in"):
            flash("Only @itbhu.ac.in email addresses are allowed.", "danger")
            return render_template("admin/student_form.html", mode="edit", student=user, token=token)
        user.email = new_email
        
        user.status = request.form.get("status", user.status)

        expiry_str = request.form.get("expiry_date", "")
        if expiry_str:
            try:
                user.expiry_date = date.fromisoformat(expiry_str)
            except ValueError:
                flash("Invalid date format.", "danger")
                return render_template("admin/student_form.html", mode="edit", student=user, token=token)

        if "photo" in request.files:
            file = request.files["photo"]
            if file.filename:
                if _allowed_file(file.filename):
                    user.photo = _save_photo(file)
                    user.photo_updated_at = datetime.utcnow()
                    user.photo_warning_scans = 0  # reset warning countdown
                else:
                    flash("Invalid photo format.", "danger")
                    return render_template("admin/student_form.html", mode="edit", student=user, token=token)

        db.session.commit()
        flash("Student updated.", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/student_form.html", mode="edit", student=user, token=token)


# ---------------------------------------------------------------------------
# Delete (deactivate) student (superadmin only)
# ---------------------------------------------------------------------------
@admin_bp.route("/students/<int:user_id>/delete", methods=["POST"])
@superadmin_required
def delete_student(user_id):
    user = User.query.get_or_404(user_id)
    
    # Unlink relationships directly via session to prevent ORM cascade tracking errors and Postgres constraint failures
    for log in user.scan_logs.all():
        log.user_id = None
    for req in user.update_requests.all():
        db.session.delete(req)
    if user.token:
        db.session.delete(user.token)
        user.token = None
        
    # Hard delete the user so their email and roll number (student_id)
    # are completely freed up and can be registered again.
    db.session.delete(user)
    db.session.commit()
    
    flash(f"Student {user.name} permanently deleted.", "warning")
    return redirect(url_for("admin.dashboard"))


# ---------------------------------------------------------------------------
# Regenerate QR (superadmin only)
# ---------------------------------------------------------------------------
@admin_bp.route("/students/<int:user_id>/regenerate", methods=["POST"])
@superadmin_required
def regenerate_qr(user_id):
    user = User.query.get_or_404(user_id)
    if user.token:
        revoke_token(user.id)
    new_token = generate_token(user.id)
    flash(f"QR regenerated for {user.name}.", "success")
    return redirect(url_for("admin.dashboard"))


# ---------------------------------------------------------------------------
# Download Raw QR Image (superadmin only)
# ---------------------------------------------------------------------------
@admin_bp.route("/students/<int:user_id>/download-qr")
@superadmin_required
def download_qr(user_id):
    user = User.query.get_or_404(user_id)
    if not user.token or user.token.is_revoked:
        flash("No active token to generate QR. Regenerate QR first.", "danger")
        return redirect(url_for("admin.dashboard"))
    
    token = user.token
    qr_bytes = generate_qr_image(token.token, token.hmac_signature)

    import io
    return send_file(
        io.BytesIO(qr_bytes),
        mimetype="image/png",
        as_attachment=True,
        download_name=f"QR_{user.student_id}.png",
    )


# ---------------------------------------------------------------------------
# Download PDF ID Card (superadmin only)
# ---------------------------------------------------------------------------
@admin_bp.route("/students/<int:user_id>/download-pdf")
@superadmin_required
def download_pdf(user_id):
    user = User.query.get_or_404(user_id)
    if not user.token or user.token.is_revoked:
        flash("No active token to generate PDF. Regenerate QR first.", "danger")
        return redirect(url_for("admin.dashboard"))
    token = user.token
    pdf_bytes = generate_id_card_pdf(user, token)

    import io
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"ID_Card_{user.student_id}.pdf",
    )


# ---------------------------------------------------------------------------
# Email QR to student (superadmin only)
# ---------------------------------------------------------------------------
@admin_bp.route("/students/<int:user_id>/email-qr", methods=["POST"])
@superadmin_required
def email_qr(user_id):
    user = User.query.get_or_404(user_id)
    if not user.token or user.token.is_revoked:
        flash("No active token to email. Regenerate QR first.", "danger")
        return redirect(url_for("admin.dashboard"))
    token = user.token
    qr_bytes = generate_qr_image(token.token, token.hmac_signature)

    if send_qr_email(user, qr_bytes):
        flash(f"QR emailed to {user.email}.", "success")
    else:
        flash("Failed to send email. Check mail configuration.", "danger")

    return redirect(url_for("admin.dashboard"))


# ---------------------------------------------------------------------------
# Scan logs (both roles – scanners see only their location)
# ---------------------------------------------------------------------------
@admin_bp.route("/scan-logs")
@superadmin_required
def scan_logs():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "").strip()

    query = ScanLog.query
    
    if search:
        query = query.join(User).filter(
            db.or_(
                User.student_id.ilike(f"%{search}%"),
                User.name.ilike(f"%{search}%"),
                User.hostel_name.ilike(f"%{search}%"),
                ScanLog.location.ilike(f"%{search}%")
            )
        )

    logs = query.order_by(ScanLog.timestamp.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    return render_template("admin/scan_logs.html", logs=logs, search=search)


# ---------------------------------------------------------------------------
# Export Scan Logs to Excel (CSV) – both roles, filtered for scanners
# ---------------------------------------------------------------------------
@admin_bp.route("/scan-logs/export")
@superadmin_required
def export_scan_logs():
    import csv
    import io
    from flask import Response
    
    logs = ScanLog.query.order_by(ScanLog.timestamp.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow([
        "Student Name", 
        "Roll Number",
        "Branch",
        "Hostel Name",
        "Location",
        "Timing (IST)",
        "Result"
    ])
    
    for log in logs:
        name = log.user.name if log.user else "Unknown"
        roll = log.user.student_id if log.user else "Unknown"
        branch = log.user.course if log.user else "Unknown"
        hostel = log.user.hostel_name if log.user and log.user.hostel_name else "N/A"
        location = log.location if log.location else "N/A"
        from datetime import timedelta
        timing = (log.timestamp + timedelta(hours=5, minutes=30)).strftime('%d %b %Y, %I:%M:%S %p') if log.timestamp else ""
        
        writer.writerow([
            name,
            roll,
            branch,
            hostel,
            location,
            timing,
            log.result
        ])
        
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=scan_logs_export.csv"}
    )

# ---------------------------------------------------------------------------
# WebQR Scanner (Admin Privileged Room)
# ---------------------------------------------------------------------------
@admin_bp.route("/scanner")
@superadmin_required
def scanner():
    """Web-based QR scanner for superadmins."""
    return render_template("admin/scanner.html")


# ---------------------------------------------------------------------------
# Scanner Account Management (superadmin only)
# ---------------------------------------------------------------------------
@admin_bp.route("/scanners")
@superadmin_required
def manage_scanners():
    """List all scanner accounts."""
    scanners = Scanner.query.order_by(Scanner.created_at.desc()).all()
    return render_template("admin/manage_scanners.html", scanners=scanners)


@admin_bp.route("/scanners/create", methods=["POST"])
@superadmin_required
def create_scanner():
    """Create a new scanner account."""
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    location_name = request.form.get("location_name", "").strip()

    errors = []
    if not all([username, password, location_name]):
        errors.append("Username, password, and location are all required.")
    if len(password) < 6:
        errors.append("Password must be at least 6 characters.")
    if Scanner.query.filter_by(username=username).first():
        errors.append(f"Username '{username}' is already taken.")

    if errors:
        for e in errors:
            flash(e, "danger")
        return redirect(url_for("admin.manage_scanners"))

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    scanner = Scanner(
        username=username,
        password_hash=hashed,
        location_name=location_name,
        plain_password=password,
    )
    db.session.add(scanner)
    db.session.commit()

    flash(f"Scanner account '{username}' created for location: {location_name}.", "success")
    return redirect(url_for("admin.manage_scanners"))


@admin_bp.route("/scanners/<int:scanner_id>/delete", methods=["POST"])
@superadmin_required
def delete_scanner(scanner_id):
    """Delete a scanner account."""
    scanner = db.session.get(Scanner, scanner_id)
    if not scanner:
        flash("Scanner account not found.", "danger")
        return redirect(url_for("admin.manage_scanners"))

    username = scanner.username
    db.session.delete(scanner)
    db.session.commit()
    flash(f"Scanner account '{username}' deleted.", "warning")
    return redirect(url_for("admin.manage_scanners"))


@admin_bp.route("/scanners/<int:scanner_id>/reset-password", methods=["POST"])
@superadmin_required
def reset_scanner_password(scanner_id):
    """Reset a scanner account's password."""
    scanner = db.session.get(Scanner, scanner_id)
    if not scanner:
        flash("Scanner account not found.", "danger")
        return redirect(url_for("admin.manage_scanners"))

    new_password = request.form.get("new_password", "").strip()
    if len(new_password) < 6:
        flash("Password must be at least 6 characters.", "danger")
        return redirect(url_for("admin.manage_scanners"))

    scanner.password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    scanner.plain_password = new_password
    db.session.commit()
    flash(f"Password reset for scanner '{scanner.username}'.", "success")
    return redirect(url_for("admin.manage_scanners"))


# ---------------------------------------------------------------------------
# Settings (superadmin only)
# ---------------------------------------------------------------------------
@admin_bp.route("/settings", methods=["GET", "POST"])
@superadmin_required
def settings():
    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "update_signature":
            if "daa_signature" in request.files:
                file = request.files["daa_signature"]
                if file.filename:
                    if _allowed_file(file.filename):
                        upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "../images")
                        os.makedirs(upload_dir, exist_ok=True)
                        file.save(os.path.join(upload_dir, "daa_signature.png"))
                        flash("Dean Academic Affairs signature updated.", "success")
                    else:
                        flash("Invalid file format. Use JPG or PNG.", "danger")

        elif action == "update_account":
            import bcrypt
            current_pass = request.form.get("current_password", "")
            new_username = request.form.get("new_username", "").strip()
            new_pass = request.form.get("new_password", "")
            confirm_pass = request.form.get("confirm_password", "")

            # Verify current password
            if not bcrypt.checkpw(current_pass.encode(), current_user.password_hash.encode()):
                flash("Incorrect current password. Changes denied.", "danger")
                return redirect(url_for("admin.settings"))

            changes_made = False

            # Update Username
            if new_username and new_username != current_user.username:
                from models import Admin
                if Admin.query.filter_by(username=new_username).first():
                    flash(f"Username '{new_username}' is already taken.", "danger")
                else:
                    current_user.username = new_username
                    changes_made = True

            # Update Password
            if new_pass:
                if new_pass != confirm_pass:
                    flash("New passwords do not match.", "danger")
                else:
                    hashed = bcrypt.hashpw(new_pass.encode(), bcrypt.gensalt()).decode()
                    current_user.password_hash = hashed
                    changes_made = True

            if changes_made:
                db.session.commit()
                flash("Account settings updated successfully.", "success")
            else:
                flash("No changes were made.", "info")

        return redirect(url_for("admin.settings"))


    sig_exists = os.path.exists(os.path.join(current_app.config["UPLOAD_FOLDER"], "../images/daa_signature.png"))
    return render_template("admin/settings.html", sig_exists=sig_exists)


# ---------------------------------------------------------------------------
# Update Requests (Student requests for photo/hostel changes)
# ---------------------------------------------------------------------------

@admin_bp.route("/requests")
@superadmin_required
def update_requests():
    """View all pending update requests."""
    status_filter = request.args.get("status", "pending")
    reqs = UpdateRequest.query.filter_by(status=status_filter).order_by(UpdateRequest.created_at.desc()).all()
    return render_template("admin/requests.html", requests=reqs, current_filter=status_filter)


@admin_bp.route("/requests/<int:req_id>/approve", methods=["POST"])
@superadmin_required
def approve_request(req_id):
    """Approve a student update request and apply changes."""
    req = db.session.get(UpdateRequest, req_id)
    if not req or req.status != "pending":
        flash("Request not found or already processed.", "danger")
        return redirect(url_for("admin.update_requests"))

    user = req.user
    if req.request_type == "photo":
        user.photo = req.new_value
        user.photo_updated_at = datetime.utcnow()
        user.photo_warning_scans = 0
    elif req.request_type == "hostel":
        user.hostel_name = req.new_value

    req.status = "approved"
    req.reviewed_at = datetime.utcnow()
    db.session.commit()

    flash(f"Approved {req.request_type} update for {user.name}.", "success")
    return redirect(url_for("admin.update_requests"))


@admin_bp.route("/requests/<int:req_id>/reject", methods=["POST"])
@superadmin_required
def reject_request(req_id):
    """Reject a student update request."""
    req = db.session.get(UpdateRequest, req_id)
    if not req or req.status != "pending":
        flash("Request not found or already processed.", "danger")
        return redirect(url_for("admin.update_requests"))

    req.status = "rejected"
    req.rejection_note = request.form.get("rejection_note", "").strip() or None
    req.reviewed_at = datetime.utcnow()

    # If it was a photo request, we can optionally delete the pending file to save space
    if req.request_type == "photo" and req.new_value:
        try:
            file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], req.new_value)
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            current_app.logger.warning(f"Failed to delete rejected photo {req.new_value}: {e}")

    db.session.commit()
    flash(f"Rejected {req.request_type} update for {req.user.name}.", "success")
    return redirect(url_for("admin.update_requests"))
