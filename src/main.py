from workers import WorkerEntrypoint
import asgi
import re

import db
import views
import uploads
from fastapi import FastAPI, Form, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
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


async def _save_with_file(env, base, upload):
    """Sube un archivo a R2 y crea la entry. Compensa (borra de R2) si falla D1."""
    content = await upload.read()
    key = uploads.make_key(upload.filename)
    width = height = None
    if base["type"] == "photo":
        width, height = uploads.image_dimensions(content)

    await uploads.store_file(env, key, content, getattr(upload, "content_type", None))
    entry_data = {
        **base,
        "file_path": key,
        "file_size": len(content),
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
    file:         list[UploadFile] = File(default=[]),
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

    # Archivos reales (FastAPI puede mandar un UploadFile vacio si no se eligio).
    files = [f for f in file if f and getattr(f, "filename", "")]

    try:
        if not files or type == "post":
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
        elif len(files) == 1:
            # Single: respeta el slug del form; si esta vacio, autogenera unico.
            up = files[0]
            slug_val = (slug.strip() if slug and slug.strip()
                        else await _unique_slug(env, _slug_base(title, up.filename)))
            await _save_with_file(env, {
                **shared,
                "title":       title,
                "description": description,
                "slug":        slug_val,
                "tags":        shared_tags,
            }, up)
        else:
            # Batch: slug autogenerado y unico por archivo (editable luego).
            for i, upload in enumerate(files):
                own_title = titles[i] if i < len(titles) else None
                own_desc = descriptions[i] if i < len(descriptions) else None
                own_tags = _split_tags(photo_tags[i]) if i < len(photo_tags) else []
                slug_val = await _unique_slug(env, _slug_base(own_title, upload.filename))
                await _save_with_file(env, {
                    **shared,
                    "title":       own_title,
                    "description": own_desc,
                    "slug":        slug_val,
                    "tags":        _merge_tags(shared_tags, own_tags),
                }, upload)

        return RedirectResponse(url="/panel?msg=Entrada_creada_correctamente", status_code=303)
    except Exception:
        return RedirectResponse(url="/panel?msg=Error", status_code=303)

@app.post("/publish/{entry_id}")
async def publish(request: Request, entry_id: int):
    env = request.scope["env"]
    await db.publish_entry(env, entry_id)
    return RedirectResponse(url="/panel", status_code=303)

@app.post("/draft/{entry_id}")
async def draft(request: Request, entry_id: int):
    env = request.scope["env"]
    await db.draft_entry(env, entry_id)
    return RedirectResponse(url="/panel", status_code=303)

@app.post("/delete/{entry_id}")
async def delete(request: Request, entry_id: int):
    env = request.scope["env"]
    await db.delete_entry(env, entry_id)
    return RedirectResponse(url="/panel", status_code=303)

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
