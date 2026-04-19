"""
Recovery routes – secure QR code recovery via OTP.
"""
from datetime import datetime, timedelta
import pyotp
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from extensions import db, limiter
from models import User, OTPRequest
from services.token_service import get_active_token
from services.qr_service import generate_qr_base64
from services.email_service import send_otp_email

recovery_bp = Blueprint("recovery", __name__, url_prefix="/recovery")


@recovery_bp.route("/", methods=["GET", "POST"])
@limiter.limit("3 per minute")
def request_recovery():
    """Step 1: User enters student ID or email to request an OTP."""
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()

        if not identifier:
            flash("Please enter your Student ID or email.", "danger")
            return render_template("recovery/request.html")

        # Find user
        user = User.query.filter(
            db.or_(User.student_id == identifier, User.email == identifier)
        ).first()

        if not user:
            # Don't reveal whether user exists — always show same message
            flash("If an account exists, an OTP has been sent to your registered email.", "info")
            return render_template("recovery/request.html")

        if user.effective_status != "active":
            flash("This ID is inactive or expired. Contact administration.", "warning")
            return render_template("recovery/request.html")

        # Rate limit: max 3 OTP requests per hour for this user
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_count = OTPRequest.query.filter(
            OTPRequest.user_id == user.id,
            OTPRequest.created_at >= one_hour_ago,
        ).count()

        if recent_count >= 3:
            flash("Too many OTP requests. Try again later.", "warning")
            return render_template("recovery/request.html")

        # Generate OTP
        otp_secret = pyotp.random_base32()
        totp = pyotp.TOTP(otp_secret, interval=current_app.config["OTP_EXPIRY_MINUTES"] * 60)
        otp_code = totp.now()

        otp_req = OTPRequest(
            user_id=user.id,
            otp_secret=otp_secret,
            expires_at=datetime.utcnow() + timedelta(minutes=current_app.config["OTP_EXPIRY_MINUTES"]),
        )
        db.session.add(otp_req)
        db.session.commit()

        # Send OTP email
        send_otp_email(user, otp_code)

        # Store OTP request ID in session
        session["recovery_otp_id"] = otp_req.id
        session["recovery_user_id"] = user.id
        # DEV MODE: When MAIL_SUPPRESS_SEND is True (no real SMTP configured),
        # surface the OTP on-screen so the portal can still be tested locally.
        # This banner never appears in production because MAIL_SUPPRESS_SEND
        # will be False when a real mail server is configured.
        if current_app.config.get("MAIL_SUPPRESS_SEND", False):
            session["dev_otp"] = otp_code  # surfaced on the OTP page

        flash("If an account exists, an OTP has been sent to your registered email.", "info")
        return redirect(url_for("recovery.verify_otp"))

    return render_template("recovery/request.html")


@recovery_bp.route("/verify-otp", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def verify_otp():
    """Step 2: User enters OTP to verify identity and recover QR."""
    otp_id = session.get("recovery_otp_id")
    user_id = session.get("recovery_user_id")

    if not otp_id or not user_id:
        flash("Please start the recovery process.", "warning")
        return redirect(url_for("recovery.request_recovery"))

    # DEV MODE: retrieve and immediately clear the dev OTP so it shows once
    dev_otp = session.pop("dev_otp", None)

    if request.method == "POST":
        submitted_otp = request.form.get("otp", "").strip()
        otp_req = db.session.get(OTPRequest, otp_id)

        if not otp_req or otp_req.is_used or otp_req.is_expired:
            flash("OTP has expired. Please request a new one.", "danger")
            session.pop("recovery_otp_id", None)
            session.pop("recovery_user_id", None)
            return redirect(url_for("recovery.request_recovery"))

        # Verify OTP
        totp = pyotp.TOTP(
            otp_req.otp_secret,
            interval=current_app.config["OTP_EXPIRY_MINUTES"] * 60,
        )

        if totp.verify(submitted_otp, valid_window=1):
            otp_req.is_used = True
            db.session.commit()

            # Get existing QR
            user = db.session.get(User, user_id)
            token = get_active_token(user.id)

            if not token:
                flash("No active ID found. Contact administration.", "danger")
                return redirect(url_for("recovery.request_recovery"))

            qr_data_uri = generate_qr_base64(token.token, token.hmac_signature)

            # Clear session
            session.pop("recovery_otp_id", None)
            session.pop("recovery_user_id", None)

            # Instantly redirect straight to the student's ID Card profile view!
            return redirect(url_for("verify.verify", token=token.token, sig=token.hmac_signature))
        else:
            flash("Invalid OTP. Please try again.", "danger")

    return render_template("recovery/otp.html", dev_otp=dev_otp)
