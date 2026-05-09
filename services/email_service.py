import io
from flask import current_app
from flask_mail import Message
from extensions import mail


def send_qr_email(user, qr_image_bytes: bytes):
    
    college = current_app.config["COLLEGE_NAME"]
    msg = Message(
        subject=f"Your {college} Digital ID Card – QR Code",
        recipients=[user.email],
    )
    msg.html = f
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

