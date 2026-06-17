"""Helpers de almacenamiento de archivos en R2.

Suben los bytes de cada archivo a un bucket R2 (binding `env.cms_media`) y extraen
metadata basica (dimensiones de imagen con Pillow). El `file_path` que se guarda
en la entry es la KEY de R2, no la URL publica.
"""

import io
import re
from uuid import uuid4

from PIL import Image

try:
    # Conversion bytes(Python) -> tipo JS aceptado por el binding R2.
    from pyodide.ffi import to_js
except ImportError:  # entorno no-Pyodide (p.ej. tests locales)
    to_js = None


_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name):
    name = (name or "archivo").strip().replace(" ", "-")
    name = _SAFE.sub("-", name)
    return name.strip("-.") or "archivo"


def make_key(name):
    return f"{uuid4()}-{sanitize_filename(name)}"


def image_dimensions(content):
    """(width, height) de una imagen, o (None, None) si no se puede leer."""
    try:
        with Image.open(io.BytesIO(content)) as img:
            return img.width, img.height
    except Exception:
        return None, None


def _to_js_bytes(content):
    if to_js is None:
        return content
    return to_js(content)


async def store_file(env, key, content, content_type=None):
    options = {}
    if content_type:
        options["httpMetadata"] = {"contentType": content_type}
    await env.cms_media.put(key, _to_js_bytes(content), **options)


async def delete_file(env, key):
    await env.cms_media.delete(key)
