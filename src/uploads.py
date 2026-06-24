"""Helpers de almacenamiento de archivos en R2.

El alta de archivos NO sube los bytes a traves del Worker: el browser hace `PUT`
directo al endpoint S3 de R2 usando una URL firmada (SigV4) que genera `presign_put`.
Asi los bytes nunca pasan por el Worker Python (Pyodide buffearia todo el body en
memoria y rompe con archivos grandes). El Worker solo firma la URL y guarda metadata.

`delete_file` sigue usando el binding R2 (`env.cms_media`) para borrar objetos.
El `file_path` que se guarda en la entry es la KEY de R2, no la URL publica.
"""

import hashlib
import hmac
import re
from datetime import datetime, timezone
from urllib.parse import quote
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


# --- Presigned PUT (AWS SigV4, S3 API de R2) --------------------------------
# Firma una URL para que el browser suba el archivo directo a R2 sin pasar por
# el Worker. Solo stdlib (hashlib/hmac), disponible en Pyodide.

def _hmac(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret, datestamp, region, service):
    k = _hmac(("AWS4" + secret).encode("utf-8"), datestamp)
    k = _hmac(k, region)
    k = _hmac(k, service)
    k = _hmac(k, "aws4_request")
    return k


def presign_put(account_id, access_key, secret_key, bucket, key,
                expires=600, region="auto"):
    """URL firmada (SigV4) para un PUT directo a R2 via su endpoint S3.

    El browser sube los bytes a esta URL; el Worker queda fuera del data path.
    Se firma solo el header `host` y se usa UNSIGNED-PAYLOAD, para que el PUT
    del browser no necesite cabeceras extra que rompan la firma.
    """
    service = "s3"
    host = f"{account_id}.r2.cloudflarestorage.com"
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")

    # La key ya viene saneada (A-Za-z0-9._-), pero codificamos por seguridad.
    canonical_uri = "/" + quote(f"{bucket}/{key}", safe="/~")

    credential_scope = f"{datestamp}/{region}/{service}/aws4_request"
    query = {
        "X-Amz-Algorithm":     "AWS4-HMAC-SHA256",
        "X-Amz-Credential":    f"{access_key}/{credential_scope}",
        "X-Amz-Date":          amz_date,
        "X-Amz-Expires":       str(expires),
        "X-Amz-SignedHeaders": "host",
    }
    canonical_querystring = "&".join(
        f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}"
        for k, v in sorted(query.items())
    )
    canonical_request = "\n".join([
        "PUT",
        canonical_uri,
        canonical_querystring,
        f"host:{host}\n",
        "host",
        "UNSIGNED-PAYLOAD",
    ])
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        amz_date,
        credential_scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])
    signing_key = _signing_key(secret_key, datestamp, region, service)
    signature = hmac.new(
        signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return (f"https://{host}{canonical_uri}?{canonical_querystring}"
            f"&X-Amz-Signature={signature}")
