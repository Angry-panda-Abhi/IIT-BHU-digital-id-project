import io
import qrcode
from qrcode.image.styledpil import StyledPilImage
from PIL import Image, ImageDraw
from flask import current_app


def generate_qr_image(token_value: str, hmac_signature: str) -> bytes:
    
    base_url = current_app.config["BASE_URL"]
    verify_url = f"{base_url}/verify?token={token_value}&sig={hmac_signature}"

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(verify_url)
    qr.make(fit=True)


    img = qr.make_image(fill_color="#1a1a2e", back_color="#ffffff").convert("RGB")


    try:
        logo_path = current_app.root_path + "/static/images/logo.png"
        logo = Image.open(logo_path).convert("RGBA")
        qr_w, qr_h = img.size
        logo_size = int(qr_w * 0.2)
        logo = logo.resize((logo_size, logo_size), Image.LANCZOS)


        mask = Image.new("L", (logo_size, logo_size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse([0, 0, logo_size, logo_size], fill=255)

        bg = Image.new("RGBA", (logo_size, logo_size), (255, 255, 255, 255))
        bg.paste(logo, (0, 0), logo)

        pos = ((qr_w - logo_size) // 2, (qr_h - logo_size) // 2)
        img.paste(bg.convert("RGB"), pos)
    except Exception:
        pass

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def generate_qr_base64(token_value: str, hmac_signature: str) -> str:
    
    import base64
    raw = generate_qr_image(token_value, hmac_signature)
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{b64}"
