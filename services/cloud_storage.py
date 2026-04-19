"""
Cloud storage service – upload images to Cloudinary.
Falls back to local storage if Cloudinary is not configured.
"""
import os
import io
from flask import current_app


def is_cloudinary_configured():
    """Check if Cloudinary credentials are set."""
    return bool(current_app.config.get("CLOUDINARY_URL"))


def upload_photo(file_storage, folder="student_photos"):
    """Upload a photo and return either a Cloudinary URL or local filename.
    
    Args:
        file_storage: werkzeug FileStorage object
        folder: Cloudinary folder name
    
    Returns:
        str: Cloudinary URL if configured, otherwise local filename
    """
    if is_cloudinary_configured():
        return _upload_to_cloudinary(file_storage, folder)
    else:
        return _save_locally(file_storage)


def upload_photo_from_path(filepath, folder="student_photos"):
    """Upload a photo from a local file path to Cloudinary.
    
    Args:
        filepath: absolute path to the file
        folder: Cloudinary folder name
    
    Returns:
        str: Cloudinary URL if configured, otherwise the original filename
    """
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
    """Upload to Cloudinary and return the secure URL."""
    import cloudinary.uploader

    # Read file into memory
    file_bytes = file_storage.read()
    file_storage.seek(0)  # Reset for any subsequent reads

    result = cloudinary.uploader.upload(
        io.BytesIO(file_bytes),
        folder=folder,
        transformation=[
            {"width": 400, "height": 500, "crop": "fill", "gravity": "face"}
        ]
    )
    return result["secure_url"]


def _save_locally(file_storage):
    """Save to local static/uploads and return the filename."""
    import time
    from werkzeug.utils import secure_filename

    filename = secure_filename(file_storage.filename)
    unique_name = f"{int(time.time())}_{filename}"
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)
    file_storage.save(os.path.join(upload_dir, unique_name))
    return unique_name


def get_photo_url(photo_value):
    """Return the correct URL for a photo value.
    
    If it's a full URL (Cloudinary), return as-is.
    If it's a local filename, return the static path.
    """
    if not photo_value:
        return None
    if photo_value.startswith("http"):
        return photo_value
    # Local file — will be resolved by url_for in templates
    return None  # Signal to use url_for('static', ...) in template
