"""Gestión segura de imágenes subidas: valida extensión y contenido real, re-codifica."""
import os
import uuid

from flask import current_app
from PIL import Image, UnidentifiedImageError
from werkzeug.datastructures import FileStorage

MAX_SIDE = 1600


class InvalidImageError(ValueError):
    pass


def _allowed_ext(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]:
        raise InvalidImageError("Formato no permitido. Usá JPG, PNG o WEBP.")
    return ext


def save_product_image(file: FileStorage) -> str:
    """Guarda la imagen con nombre aleatorio y devuelve el nombre de archivo.

    La imagen se abre con Pillow y se vuelve a guardar: esto descarta archivos
    que no son imágenes reales y elimina metadatos/payloads embebidos.
    """
    if not file or not file.filename:
        raise InvalidImageError("No se seleccionó ningún archivo.")
    _allowed_ext(file.filename)
    try:
        img = Image.open(file.stream)
        img.verify()
        file.stream.seek(0)
        img = Image.open(file.stream)
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError("El archivo no es una imagen válida.") from exc

    img.thumbnail((MAX_SIDE, MAX_SIDE))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.getbands() else "RGB")

    filename = f"{uuid.uuid4().hex}.webp"
    folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(folder, exist_ok=True)
    img.save(os.path.join(folder, filename), "WEBP", quality=85)
    return filename


def delete_product_image_file(filename: str) -> None:
    folder = current_app.config["UPLOAD_FOLDER"]
    path = os.path.realpath(os.path.join(folder, filename))
    if path.startswith(os.path.realpath(folder)) and os.path.isfile(path):
        os.remove(path)
