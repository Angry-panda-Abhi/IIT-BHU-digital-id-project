import os
import io
from flask import current_app


def is_cloudinary_configured():
    
    return bool(current_app.config.get("CLOUDINARY_URL"))


def upload_photo(file_storage, folder="student_photos"):
    
    if is_cloudinary_configured():
        return _upload_to_cloudinary(file_storage, folder)
    else:
        return _save_locally(file_storage)


def upload_photo_from_path(filepath, folder="student_photos"):
    
    if is_cloudinary_configured():
        import cloudinary.uploader
        result = cloudinary.uploader.upload(
            filepath,
            folder=folder,
            transformation=[
                {"width": 400, "height": 500, "crop": "fill", "gravity": "face"}
            ]
        )
        return result["secure_url"]
    return os.path.basename(filepath)


def _upload_to_cloudinary(file_storage, folder):
    
    import cloudinary.uploader
    from flask import flash

    try:

        file_bytes = file_storage.read()
        file_storage.seek(0)

        result = cloudinary.uploader.upload(
            io.BytesIO(file_bytes),
            folder=folder,
            transformation=[
                {"width": 400, "height": 500, "crop": "fill", "gravity": "face"}
            ]
        )
        return result["secure_url"]
    except Exception as e:
        current_app.logger.error(f"❌ Cloudinary upload failed: {e}")
        flash(f"Cloudinary upload failed ({e}). Saving locally instead.", "warning")

        return _save_locally(file_storage)


def _save_locally(file_storage):
    
    import time
    from werkzeug.utils import secure_filename

    filename = secure_filename(file_storage.filename)
    unique_name = f"{int(time.time())}_{filename}"
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)
    file_storage.save(os.path.join(upload_dir, unique_name))
    return unique_name


def get_photo_url(photo_value):
    
    if not photo_value:
        return None
    if photo_value.startswith("http"):
        return photo_value

    return None
