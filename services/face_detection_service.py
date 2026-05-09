import cv2
from werkzeug.datastructures import FileStorage
from PIL import Image
import io
import numpy as np

face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def _load_image_array(file: FileStorage):
    image_data = file.read()
    file.seek(0)
    image = Image.open(io.BytesIO(image_data))
    image = image.convert("RGB")
    return np.array(image)


def validate_photo_has_face(file: FileStorage, min_face_size=(80, 80)):
    try:
        image_array = _load_image_array(file)
        gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=min_face_size)
        face_count = len(faces)

        if face_count == 0:
            return False, "No face detected in the photo. Please upload a clear photo of your face."
        if face_count > 1:
            return False, f"Multiple faces detected ({face_count} faces found). Please upload a photo with only your face."
        return True, "Photo is valid. Exactly one face detected."

    except Exception as e:
        return False, f"Error processing photo: {str(e)[:100]}"


def validate_photo_quality(file: FileStorage, min_width=300, min_height=300):
    try:
        image_data = file.read()
        file.seek(0)
        image = Image.open(io.BytesIO(image_data))
        width, height = image.size
        if width < min_width or height < min_height:
            return False, f"Photo resolution too low. Minimum {min_width}x{min_height}px required. Current: {width}x{height}px"
        return True, "Photo quality is acceptable."
    except Exception as e:
        return False, f"Error checking photo quality: {str(e)[:100]}"


def validate_registration_photo(file: FileStorage):
    if not file or not file.filename:
        return False, "No photo provided."

    quality_valid, quality_msg = validate_photo_quality(file)
    if not quality_valid:
        return False, quality_msg

    face_valid, face_msg = validate_photo_has_face(file)
    if not face_valid:
        return False, face_msg

    return True, "Photo accepted. Registration can proceed."
