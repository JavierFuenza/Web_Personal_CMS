"""Helpers de almacenamiento de archivos en R2.

Suben los bytes de cada archivo a un bucket R2 (binding `env.cms_media`) y extraen
width/height leyendo el header de la imagen (sin Pillow, para no inflar el bundle
del Worker por encima del limite de tamano). El `file_path` que se guarda en la
entry es la KEY de R2, no la URL publica.
"""

import re
from uuid import uuid4

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


# --- Lectura de dimensiones por header (PNG/GIF/JPEG/WebP) -------------------

def _png(data):
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    return None, None


def _gif(data):
    if len(data) >= 10 and data[:6] in (b"GIF87a", b"GIF89a"):
        return int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")
    return None, None


def _jpeg(data):
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None, None
    i, n = 2, len(data)
    while i < n:
        if data[i] != 0xFF:
            i += 1
            continue
        while i < n and data[i] == 0xFF:
            i += 1
        if i >= n:
            break
        marker = data[i]
        i += 1
        # Marcadores sin payload: SOI/EOI/RSTn.
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        if i + 1 >= n:
            break
        seg_len = (data[i] << 8) | data[i + 1]
        # SOFn (contiene dimensiones), excepto DHT/JPG/DAC.
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            if i + 6 < n:
                height = (data[i + 3] << 8) | data[i + 4]
                width = (data[i + 5] << 8) | data[i + 6]
                return width, height
            break
        i += seg_len
    return None, None


def _webp(data):
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None, None
    fmt = data[12:16]
    if fmt == b"VP8 ":
        width = (data[26] | (data[27] << 8)) & 0x3FFF
        height = (data[28] | (data[29] << 8)) & 0x3FFF
        return width, height
    if fmt == b"VP8L":
        bits = data[21] | (data[22] << 8) | (data[23] << 16) | (data[24] << 24)
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if fmt == b"VP8X":
        width = (data[24] | (data[25] << 8) | (data[26] << 16)) + 1
        height = (data[27] | (data[28] << 8) | (data[29] << 16)) + 1
        return width, height
    return None, None


def image_dimensions(content):
    """(width, height) de una imagen, o (None, None) si no se puede leer."""
    try:
        for parser in (_png, _gif, _jpeg, _webp):
            w, h = parser(content)
            if w and h:
                return w, h
    except Exception:
        pass
    return None, None


# --- R2 ---------------------------------------------------------------------

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
