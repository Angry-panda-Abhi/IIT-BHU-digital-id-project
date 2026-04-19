"""
Email service – send QR codes and OTP emails.
Uses Flask-Mail; in development mode, emails are printed to the console.
"""
import io
from flask import current_app
from flask_mail import Message
from extensions import mail


def send_qr_email(user, qr_image_bytes: bytes):
    """
    Email the QR code image to a student.
    """
    college = current_app.config["COLLEGE_NAME"]
    msg = Message(
        subject=f"Your {college} Digital ID Card – QR Code",
        recipients=[user.email],
    )
    msg.html = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 520px; margin: auto;
                background: #0f0c29; color: #fff; border-radius: 12px; padding: 32px;">
        <h2 style="color: #6c63ff; margin-top: 0;">{college}</h2>
        <p>Hello <strong>{user.name}</strong>,</p>
        <p>Your secure digital ID card QR code is attached to this email.
           Present this QR code for identity verification on campus.</p>
        <p style="color: #aaa; font-size: 13px;">
           Student ID: {user.student_id}<br>
           Course: {user.course}<br>
           Valid until: {user.expiry_date.strftime('%d %b %Y')}
        </p>
        <p style="color: #ff9100; font-size: 12px;">
           ⚠️ Do not share this QR code with anyone. It is uniquely linked to your identity.
        </p>
        <p style="color: #666; font-size: 11px;">— {college} ID System</p>
    </div>
    """
    msg.attach(
        "id_qr_code.png",
        "image/png",
        qr_image_bytes,
    )

    try:
        mail.send(msg)
        current_app.logger.info(f"QR email sent to {user.email}")
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send QR email to {user.email}: {e}")
        return False


def send_otp_email(user, otp_code: str):
    """
    Email a one-time password for QR recovery.
    """
    college = current_app.config["COLLEGE_NAME"]
    expiry_min = current_app.config["OTP_EXPIRY_MINUTES"]
    msg = Message(
        subject=f"{college} – QR Recovery OTP",
        recipients=[user.email],
    )
    msg.html = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 480px; margin: auto;
                background: #0f0c29; color: #fff; border-radius: 12px; padding: 32px;">
        <h2 style="color: #6c63ff; margin-top: 0;">QR Code Recovery</h2>
        <p>Hello <strong>{user.name}</strong>,</p>
        <p>Your one-time verification code is:</p>
        <div style="text-align: center; margin: 24px 0;">
            <span style="font-size: 32px; font-weight: 700; letter-spacing: 8px;
                         color: #00c853; background: #1a1a2e; padding: 12px 24px;
                         border-radius: 8px;">{otp_code}</span>
        </div>
        <p style="color: #aaa; font-size: 13px;">
            This code expires in <strong>{expiry_min} minutes</strong>.<br>
            If you did not request this, please ignore this email.
        </p>
        <p style="color: #666; font-size: 11px;">— {college} ID System</p>
    </div>
    """

    try:
        mail.send(msg)
        current_app.logger.info(f"OTP email sent to {user.email}")
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send OTP email to {user.email}: {e}")
        return False
