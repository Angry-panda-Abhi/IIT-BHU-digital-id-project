"""
PDF ID card generation service using ReportLab.
"""
import io
import os
from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from flask import current_app
from services.qr_service import generate_qr_image


# Card dimensions (standard CR80 card: 85.6 × 53.98 mm)
CARD_W = 86 * mm
CARD_H = 54 * mm


def generate_id_card_pdf(user, token) -> bytes:
    """
    Generate a styled PDF ID card matching the requested light-mode template.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(CARD_W, CARD_H))
    college = current_app.config.get("COLLEGE_NAME", "INDIAN INSTITUTE OF TECHNOLOGY, VARANASI").upper()
    
    # --- Background ---
    c.setFillColor(white)
    c.rect(0, 0, CARD_W, CARD_H, fill=1, stroke=0)

    # --- Right Vertical Bar ---
    c.setFillColor(HexColor("#432d6d")) # Dark purple
    c.rect(81 * mm, 0, 5 * mm, 54 * mm, fill=1, stroke=0)
    
    c.saveState()
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 6)
    c.translate(83.5 * mm, 27 * mm)
    c.rotate(90)
    c.drawCentredString(0, 0, "Student Card")
    c.restoreState()

    # --- Logo & Header ---
    logo_path = os.path.join(current_app.config["UPLOAD_FOLDER"], "../images/logo.png")
    if os.path.exists(logo_path):
        try:
            # Draw the round IIT BHU logo at the upper left
            c.drawImage(ImageReader(logo_path), 2 * mm, 38 * mm, 14 * mm, 14 * mm, preserveAspectRatio=True, mask="auto")
        except Exception:
            pass

    header_path = os.path.join(current_app.config["UPLOAD_FOLDER"], "../images/iit_header.png")
    if os.path.exists(header_path):
        try:
            # Draw the wide IIT BHU typography graphic shifted
            c.drawImage(ImageReader(header_path), 17 * mm, 38 * mm, 62 * mm, 14 * mm, preserveAspectRatio=True, mask="auto")
        except Exception:
            pass

    # --- Student Details ---
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 6.0)
    
    dob_str = user.dob.strftime('%d-%b-%Y') if user.dob else "N/A"
    dept_str = user.department.upper() if user.department else "N/A"
    
    labels = ["Roll.No", "Name", "Course", "Dept", "D.O.B.", "Status"]
    values = [user.student_id, user.name, user.course.upper() if user.course else "N/A", dept_str, dob_str, user.effective_status.upper()]
    
    cur_y = 35 * mm
    for label, val in zip(labels, values):
        c.drawString(22 * mm, cur_y, label)
        c.drawString(34 * mm, cur_y, f": {val}")
        cur_y -= 4 * mm

    # --- Student Photo ---
    photo_x = 4 * mm
    photo_y = 15 * mm
    photo_w = 16 * mm
    photo_h = 20 * mm

    if user.photo:
        try:
            if user.photo.startswith("http"):
                # Cloudinary URL — download into memory
                import urllib.request
                photo_data = io.BytesIO(urllib.request.urlopen(user.photo).read())
                photo_reader = ImageReader(photo_data)
            else:
                # Local file
                local_path = os.path.join(current_app.config["UPLOAD_FOLDER"], user.photo)
                if not os.path.exists(local_path):
                    raise FileNotFoundError("Local photo missing")
                photo_reader = ImageReader(local_path)
            
            c.drawImage(
                photo_reader,
                photo_x, photo_y, photo_w, photo_h,
                preserveAspectRatio=False, mask="auto",
            )
        except Exception:
            _draw_placeholder(c, photo_x, photo_y, photo_w, photo_h)
    else:
        _draw_placeholder(c, photo_x, photo_y, photo_w, photo_h)

    # Border around photo
    c.setStrokeColor(black)
    c.setLineWidth(0.5)
    c.rect(photo_x, photo_y, photo_w, photo_h, fill=0, stroke=1)

    # --- QR Code ---
    # Placing QR code on the right side next to details
    if token:
        qr_bytes = generate_qr_image(token.token, token.hmac_signature)
        qr_reader = ImageReader(io.BytesIO(qr_bytes))
        qr_size = 23 * mm
        qr_x = 57 * mm
        qr_y = 5 * mm
        c.drawImage(qr_reader, qr_x, qr_y, qr_size, qr_size)

    # --- Footer Information ---
    c.setFillColor(black)
    
    # Validity
    c.setFont("Helvetica-Bold", 5.5)
    c.drawString(4 * mm, 4 * mm, f"Valid Upto: {user.expiry_date.strftime('%d-%b-%Y')}")
    
    # Signatures
    c.setFont("Helvetica", 5)
    c.drawString(35 * mm, 3 * mm, "Dean Academic Affairs")
    
    sig_path = os.path.join(current_app.config["UPLOAD_FOLDER"], "../images/daa_signature.png")
    if os.path.exists(sig_path):
        try:
            # Draw signature image safely above the text
            c.drawImage(ImageReader(sig_path), 33 * mm, 4.5 * mm, 18 * mm, 5 * mm, preserveAspectRatio=True, mask="auto")
        except Exception:
            pass
    
    c.save()
    buf.seek(0)
    return buf.getvalue()


def _draw_placeholder(c, x, y, w, h):
    """Draw a placeholder rectangle when no photo is available."""
    c.setFillColor(white)
    c.rect(x, y, w, h, fill=1, stroke=1)
    c.setFillColor(HexColor("#777777"))
    c.setFont("Helvetica", 5)
    c.drawCentredString(x + w / 2, y + h / 2, "No Photo")
