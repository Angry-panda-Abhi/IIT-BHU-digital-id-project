"""
Scanner routes – dedicated room for QR verification terminals.
"""
from datetime import datetime
from functools import wraps
import csv
import io

import bcrypt
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, session, g, Response
)

from extensions import db, limiter
from models import Scanner, ScanLog

scanner_bp = Blueprint("scanner", __name__, url_prefix="/scanner")

def scanner_required(f):
    """Decorator: requires the user to be logged in via the isolated Scanner session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if getattr(g, 'active_scanner', None):
            return f(*args, **kwargs)
        flash("Scanner access required.", "danger")
        return redirect(url_for("scanner.login"))
    return decorated

@scanner_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    """Isolated login page exclusively for Scanner accounts."""
    if getattr(g, 'active_scanner', None):
        return redirect(url_for("scanner.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        scanner_user = Scanner.query.filter_by(username=username).first()

        if scanner_user and bcrypt.checkpw(password.encode(), scanner_user.password_hash.encode()):
            session["scanner_auth_id"] = scanner_user.id
            flash(f"Scanner active — {scanner_user.location_name}", "success")
            return redirect(url_for("scanner.dashboard"))

        flash("Invalid scanner credentials.", "danger")

    return render_template("scanner/login.html")

@scanner_bp.route("/logout")
def logout():
    """Terminal logout sequence for this specific Scanner room."""
    session.pop("scanner_auth_id", None)
    flash("Scanner session ended.", "info")
    return redirect(url_for("index"))

@scanner_bp.route("/dashboard")
@scanner_required
def dashboard():
    """Isolated dashboard for the active scanner."""
    active_scanner = getattr(g, 'active_scanner')
        
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    scans_today = ScanLog.query.filter(
        ScanLog.location == active_scanner.location_name,
        ScanLog.timestamp >= today_start
    ).count()
    
    return render_template("scanner/dashboard.html", scans_today=scans_today)

@scanner_bp.route("/scan")
@scanner_required
def scan():
    """Web-based QR scanner room."""
    return render_template("scanner/scan.html")

@scanner_bp.route("/scan-logs")
@scanner_required
def scan_logs():
    """Scan logs limited to this specific scanner's location."""
    page = request.args.get("page", 1, type=int)
    active_scanner = getattr(g, 'active_scanner')

    logs = ScanLog.query.filter_by(location=active_scanner.location_name).order_by(ScanLog.timestamp.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    return render_template("admin/scan_logs.html", logs=logs)

@scanner_bp.route("/scan-logs/export")
@scanner_required
def export_scan_logs():
    """Export Scan Logs strictly for this scanner's location."""
    active_scanner = getattr(g, 'active_scanner')
    logs = ScanLog.query.filter_by(location=active_scanner.location_name).order_by(ScanLog.timestamp.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow([
        "Serial Number", "Student Name", "Roll Number", "Branch", 
        "Hostel Name", "Location", "Timing", "Result"
    ])
    
    for log in logs:
        name = log.user.name if log.user else "Unknown"
        roll = log.user.student_id if log.user else "Unknown"
        branch = log.user.course if log.user else "Unknown"
        hostel = log.user.hostel_name if log.user and log.user.hostel_name else "N/A"
        location = log.location if log.location else "N/A"
        timing = log.timestamp.strftime('%Y-%m-%d %H:%M:%S') if log.timestamp else ""
        
        writer.writerow([
            log.id, name, roll, branch, hostel, location, timing, log.result
        ])
        
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=scanner_logs_export.csv"}
    )
