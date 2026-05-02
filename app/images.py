from PIL import Image
import os
from uuid import uuid4

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def create_thumbnail(
    original_path: str, thumbnail_path: str, max_size: tuple = (300, 300)
):
    with Image.open(original_path) as img:
        img = img.convert("RGB")
        img.thumbnail(max_size, Image.LANCZOS)
        img.save(thumbnail_path, "JPEG", quality=85)


def get_content_type(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(ext, "image/jpeg")


def generate_photo_filename(plant_id: int) -> str:
    return f"{plant_id}/{uuid4().hex}"
