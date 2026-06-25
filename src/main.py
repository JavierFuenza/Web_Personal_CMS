from workers import WorkerEntrypoint
import asgi
import re

import db
import views
import uploads
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from jinja2 import Environment, DictLoader, select_autoescape

app = FastAPI()

# Templates embebidos (sin filesystem en runtime). /static lo sirve Workers
# Assets (ver wrangler.toml), no FastAPI.
_jinja = Environment(
    loader=DictLoader(views.TEMPLATES),
    autoescape=select_autoescape(["html", "xml"]),
)


def render(name, **context):
    return HTMLResponse(_jinja.get_template(name).render(**context))


# El runtime de Workers provee el servidor ASGI; este entrypoint le pasa la
# app FastAPI y el `env` (bindings: D1, etc.). No se usa uvicorn.
class Default(WorkerEntrypoint):
    async def fetch(self, request):
        return await asgi.fetch(app, request, self.env)


@app.get("/init")
async def init(request: Request):
    env = request.scope["env"]
    await db.init_db(env)
    return {"status": "ok"}

@app.get("/panel", response_class=HTMLResponse)
async def panel(request: Request):
    env = request.scope["env"]
    return render("panel.html", entries=await db.get_all(env), request=request)

@app.get("/form", response_class=HTMLResponse)
async def form_get(request: Request):
    return render("form.html", request=request)


@app.post("/upload-url")
async def upload_url(request: Request):
    """Firma una URL de subida directa a R2 para el archivo que indica el cliente.

    El browser hace el PUT a esa URL; los bytes no pasan por el Worker.
    """
    env = request.scope["env"]
    data = await request.json()
    key = uploads.make_key(data.get("filename") or "archivo")
    url = uploads.presign_put(
        env.R2_ACCOUNT_ID,
        env.R2_ACCESS_KEY_ID,
        env.R2_SECRET_ACCESS_KEY,
        env.R2_BUCKET,
        key,
    )
    return {"key": key, "url": url}

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text):
    return _SLUG_RE.sub("-", (text or "").strip().lower()).strip("-")


def _slug_base(title, filename):
    """Base de slug a partir del titulo; si no hay, del nombre de archivo."""
    name_no_ext = (filename or "").rsplit(".", 1)[0]
    return slugify(title) or slugify(name_no_ext) or "foto"


async def _unique_slug(env, base):
    """Garantiza unicidad agregando sufijo -2, -3... si ya existe."""
    slug = base
    n = 2
    while await db.slug_exists(env, slug):
        slug = f"{base}-{n}"
        n += 1
    return slug


def _split_tags(raw):
    return [t.strip() for t in (raw or "").split(',') if t.strip()]


def _merge_tags(*lists):
    """Une listas de tags preservando orden y sin duplicados."""
    seen, out = set(), []
    for lst in lists:
        for tag in lst:
            if tag and tag not in seen:
                seen.add(tag)
                out.append(tag)
    return out


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def _save_entry_with_meta(env, base, key, size, width, height):
    """Crea la entry para un archivo YA subido a R2 (el browser hizo el PUT).

    Compensa borrando el objeto de R2 si falla la insercion en D1.
    """
    entry_data = {
        **base,
        "file_path": key,
        "file_size": size,
        "width":     width,
        "height":    height,
        "duration":  None,
    }
    try:
        await db.create_entry(env, entry_data)
    except Exception:
        await uploads.delete_file(env, key)
        raise


@app.post("/form")
async def form_post(
    request:      Request,
    type:         str = Form(default=None),
    title:        str = Form(default=None),
    description:  str = Form(default=None),
    body:         str = Form(default=None),
    slug:         str = Form(default=None),
    taken_at:     str = Form(default=None),
    is_analog:    str = Form(default=None),
    camera_model: str = Form(default=None),
    film_stock:   str = Form(default=None),
    album:        str = Form(default=None),
    tags:         str = Form(default=None),
    # Metadata de archivos YA subidos a R2 por el browser (arrays paralelos).
    # El Worker no recibe bytes: solo la KEY de R2, nombre, tamano y dimensiones.
    file_keys:    list[str] = Form(default=[]),
    file_names:   list[str] = Form(default=[]),
    file_sizes:   list[str] = Form(default=[]),
    widths:       list[str] = Form(default=[]),
    heights:      list[str] = Form(default=[]),
    titles:       list[str] = Form(default=[]),
    descriptions: list[str] = Form(default=[]),
    photo_tags:   list[str] = Form(default=[]),
):
    env = request.scope["env"]
    shared_tags = _split_tags(tags)

    # Campos compartidos comunes a single y batch (sin slug: se resuelve por entry).
    shared = {
        "type":         type,
        "body":         body,
        "taken_at":     taken_at,
        "is_analog":    1 if is_analog == "on" else 0,
        "camera_model": camera_model,
        "film_stock":   film_stock,
        "album":        album,
    }

    def _meta(i):
        """(name, size, width, height) del archivo i de los arrays paralelos."""
        name = file_names[i] if i < len(file_names) else ""
        size = _int_or_none(file_sizes[i]) if i < len(file_sizes) else None
        w = _int_or_none(widths[i]) if i < len(widths) else None
        h = _int_or_none(heights[i]) if i < len(heights) else None
        return name, size, w, h

    try:
        if not file_keys or type == "post":
            # Sin archivo (incluye posts): el slug lo pone el usuario (o NULL).
            await db.create_entry(env, {
                **shared,
                "title":       title,
                "description": description,
                "slug":        slug.strip() if slug and slug.strip() else None,
                "tags":        shared_tags,
                "file_path":   None,
                "file_size":   None,
                "width":       None,
                "height":      None,
                "duration":    None,
            })
        elif len(file_keys) == 1:
            # Single: respeta el slug del form; si esta vacio, autogenera unico.
            name, size, w, h = _meta(0)
            slug_val = (slug.strip() if slug and slug.strip()
                        else await _unique_slug(env, _slug_base(title, name)))
            await _save_entry_with_meta(env, {
                **shared,
                "title":       title,
                "description": description,
                "slug":        slug_val,
                "tags":        shared_tags,
            }, file_keys[0], size, w, h)
        else:
            # Batch: slug autogenerado y unico por archivo (editable luego).
            for i, key in enumerate(file_keys):
                name, size, w, h = _meta(i)
                own_title = titles[i] if i < len(titles) else None
                own_desc = descriptions[i] if i < len(descriptions) else None
                own_tags = _split_tags(photo_tags[i]) if i < len(photo_tags) else []
                slug_val = await _unique_slug(env, _slug_base(own_title, name))
                await _save_entry_with_meta(env, {
                    **shared,
                    "title":       own_title,
                    "description": own_desc,
                    "slug":        slug_val,
                    "tags":        _merge_tags(shared_tags, own_tags),
                }, key, size, w, h)

        return RedirectResponse(url="/panel?msg=Entrada_creada_correctamente", status_code=303)
    except Exception:
        return RedirectResponse(url="/panel?msg=Error", status_code=303)

@app.post("/entries/bulk")
async def entries_bulk(request: Request):
    env = request.scope["env"]
    try:
        data = await request.json()
        action = data.get("action")
        ids = [int(i) for i in (data.get("ids") or [])]
    except Exception:
        return JSONResponse({"ok": False}, status_code=400)
    if action not in ("publish", "draft", "delete") or not ids:
        return JSONResponse({"ok": False}, status_code=400)

    if action == "publish":
        count = await db.publish_bulk(env, ids)
    elif action == "draft":
        count = await db.draft_bulk(env, ids)
    else:
        # Borrar primero el objeto R2 (si lo hay) para no dejar huerfanos.
        for entry_id in ids:
            entry, _ = await db.get_detail(env, entry_id)
            if entry and entry.get("file_path"):
                try:
                    await uploads.delete_file(env, entry["file_path"])
                except Exception:
                    pass  # no bloquear el borrado si R2 falla
        count = await db.delete_bulk(env, ids)

    return JSONResponse({"ok": True, "count": count})

@app.get("/editar/{entry_id}", response_class=HTMLResponse)
async def edit_get(request: Request, entry_id: int):
    env = request.scope["env"]
    entry, tags = await db.get_detail(env, entry_id)
    return render(
        "edit.html",
        entry=entry,
        tags=", ".join([t["tag_name"] for t in tags]),
    )

@app.post("/editar/{entry_id}")
async def edit_post(
    request:      Request,
    entry_id:     int,
    type:         str = Form(default=None),
    title:        str = Form(default=None),
    description:  str = Form(default=None),
    body:         str = Form(default=None),
    slug:         str = Form(default=None),
    taken_at:     str = Form(default=None),
    is_analog:    str = Form(default=None),
    camera_model: str = Form(default=None),
    film_stock:   str = Form(default=None),
    album:        str = Form(default=None),
    tags:         str = Form(default=None),
):
    env = request.scope["env"]
    entry, _ = await db.get_detail(env, entry_id)

    entry_data = {
        "type":         type,
        "title":        title,
        "description":  description,
        "body":         body,
        "slug":         slug,
        "taken_at":     taken_at,
        "is_analog":    1 if is_analog == "on" else 0,
        "camera_model": camera_model,
        "film_stock":   film_stock,
        "album":        album,
        "tags":         [t.strip() for t in (tags or "").split(',') if t.strip()],
        "file_path":    entry["file_path"],
        "file_size":    entry["file_size"],
        "width":        entry["width"],
        "height":       entry["height"],
        "duration":     entry["duration"],
    }
    await db.update_entry(env, entry_id, entry_data)
    return RedirectResponse(url="/panel", status_code=303)
