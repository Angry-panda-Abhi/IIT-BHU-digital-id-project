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

