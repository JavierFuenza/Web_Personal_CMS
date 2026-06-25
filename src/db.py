"""Capa de datos sobre Cloudflare D1.

D1 es SQLite gestionado, pero su binding es ASINCRONO y solo acepta
parametros POSICIONALES (?). No hay filesystem en runtime, asi que el SQL
va embebido como constantes en vez de leerse desde sql/*.sql.

Cada funcion recibe `env` (el binding del Worker). Se accede a la base via
`env.cms`, donde "DB" es el binding declarado en wrangler.toml.
"""

# --- SQL embebido -----------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS album (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS tag (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS entry (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    type         TEXT NOT NULL CHECK(type IN ('photo', 'video', 'post')),
    title        TEXT,
    description  TEXT,
    body         TEXT,
    slug         TEXT UNIQUE,
    file_path    TEXT,
    file_size    INTEGER,
    width        INTEGER,
    height       INTEGER,
    taken_at     TEXT,
    is_analog    INTEGER DEFAULT 0 CHECK(is_analog IN (0, 1)),
    camera_model TEXT,
    film_stock   TEXT,
    duration     INTEGER,
    album_id     INTEGER REFERENCES album(id) ON DELETE SET NULL,
    status       TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'published')),
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    published_at TEXT
);

CREATE TABLE IF NOT EXISTS entry_tag (
    entry_id INTEGER NOT NULL REFERENCES entry(id) ON DELETE CASCADE,
    tag_id   INTEGER NOT NULL REFERENCES tag(id)   ON DELETE CASCADE,
    PRIMARY KEY (entry_id, tag_id)
);
"""

GET_ALL = """
SELECT e.id, e.title, e.description, e.type, e.status, e.published_at, e.file_path, a.name AS album_name
FROM entry e
LEFT JOIN album a ON e.album_id = a.id
"""

GET_DETAIL = """
SELECT e.id, e.type, e.title, e.description, e.body, e.slug, e.file_path, e.file_size, e.width, e.height, e.taken_at, e.is_analog, e.camera_model, e.film_stock, e.duration, e.status, e.created_at, e.published_at, a.name AS album_name
FROM entry e
LEFT JOIN album a ON e.album_id = a.id
WHERE e.id = ?
"""

GET_ENTRY_TAGS = """
SELECT e.id AS entry_id, t.name AS tag_name
FROM entry e
INNER JOIN entry_tag et ON e.id = et.entry_id
INNER JOIN tag t ON et.tag_id = t.id
WHERE e.id = ?
"""

GET_BY_TYPE = """
SELECT e.id, e.title, e.description, e.type, e.status, e.published_at, e.file_path, a.name AS album_name
FROM entry e
LEFT JOIN album a ON e.album_id = a.id
WHERE type = ?
"""

GET_BY_STATUS = """
SELECT e.id, e.title, e.description, e.type, e.status, e.published_at, e.file_path, a.name AS album_name
FROM entry e
LEFT JOIN album a ON e.album_id = a.id
WHERE status = ?
"""

GET_ALBUMS = "SELECT id, name FROM album"

GET_ALBUM_ENTRY = """
SELECT e.id, e.title, e.file_path, a.id as album_id, a.name
FROM entry e
JOIN album a ON e.album_id = a.id
WHERE a.id = ?
"""

GET_BY_TAG = """
SELECT e.id, e.title, e.description, e.type, e.status, e.published_at, e.file_path, t.id as tag_id, t.name
FROM entry e
INNER JOIN entry_tag et ON e.id = et.entry_id
INNER JOIN tag t ON et.tag_id = t.id
WHERE t.id = ?
"""

GET_TAGS = "SELECT id, name FROM tag"
GET_TAG_ID = "SELECT id FROM tag WHERE name = ?"
GET_ALBUM_ID = "SELECT id FROM album WHERE name = ?"
SLUG_EXISTS = "SELECT 1 FROM entry WHERE slug = ? LIMIT 1"

CREATE_TAG = "INSERT OR IGNORE INTO tag (name) VALUES (?)"
CREATE_ALBUM = "INSERT OR IGNORE INTO album (name) VALUES (?)"

# Parametros posicionales en el orden de las columnas (D1 no soporta :nombre).
CREATE_ENTRY = """
INSERT INTO entry(type, title, description, body, slug, file_path, file_size, width, height, taken_at, is_analog, camera_model, film_stock, duration, album_id)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

CREATE_ENTRY_TAG = "INSERT OR IGNORE INTO entry_tag (tag_id, entry_id) VALUES (?, ?)"

UPDATE_ENTRY = """
UPDATE entry SET
    type = ?, title = ?, description = ?, body = ?, slug = ?,
    file_path = ?, file_size = ?, width = ?, height = ?, taken_at = ?,
    is_analog = ?, camera_model = ?, film_stock = ?, duration = ?, album_id = ?,
    status = ?, published_at = ?
WHERE id = ?
"""

DELETE_ENTRY = "DELETE FROM entry WHERE id = ?"
PUBLISH_ENTRY = 'UPDATE entry SET status = "published" WHERE id = ?'
DRAFT_ENTRY = 'UPDATE entry SET status = "draft" WHERE id = ?'

# Elimina albums sin ninguna entry asociada (huerfanos tras borrar/editar).
DELETE_ORPHAN_ALBUMS = (
    "DELETE FROM album WHERE id NOT IN "
    "(SELECT album_id FROM entry WHERE album_id IS NOT NULL)"
)

# Elimina tags que ya no estan asociadas a ninguna entry (entry_tag se vacia
# por ON DELETE CASCADE al borrar la entry, dejando la tag huerfana).
DELETE_ORPHAN_TAGS = "DELETE FROM tag WHERE id NOT IN (SELECT tag_id FROM entry_tag)"


# --- Helpers de conversion de resultados ------------------------------------
# D1 devuelve objetos JS (JsProxy en Pyodide). Los convertimos a dict/list de
# Python para que las plantillas Jinja2 puedan usar acceso por clave: row["x"].

def _to_dict(row):
    if row is None:
        return None
    to_py = getattr(row, "to_py", None)
    if to_py is not None:
        return to_py()
    return dict(row)


def _to_list(res):
    rows = res.results
    to_py = getattr(rows, "to_py", None)
    if to_py is not None:
        return to_py()
    return [_to_dict(r) for r in rows]


# --- Configurar db ----------------------------------------------------------

async def init_db(env):
    statements = [s.strip() for s in SCHEMA_SQL.split(";") if s.strip()]
    await env.cms.batch([env.cms.prepare(s) for s in statements])


# --- Lecturas ---------------------------------------------------------------

async def get_all(env):
    return _to_list(await env.cms.prepare(GET_ALL).all())


async def get_tags(env):
    return _to_list(await env.cms.prepare(GET_TAGS).all())


async def get_entry_tags(env, entry_id):
    return _to_list(await env.cms.prepare(GET_ENTRY_TAGS).bind(entry_id).all())


async def get_by_type(env, entry_type):
    return _to_list(await env.cms.prepare(GET_BY_TYPE).bind(entry_type).all())


async def get_detail(env, entry_id):
    entry = _to_dict(await env.cms.prepare(GET_DETAIL).bind(entry_id).first())
    tags = await get_entry_tags(env, entry_id)
    return entry, tags


async def get_by_status(env, entry_status):
    return _to_list(await env.cms.prepare(GET_BY_STATUS).bind(entry_status).all())


async def get_albums(env):
    return _to_list(await env.cms.prepare(GET_ALBUMS).all())


async def get_album_entry(env, album_id):
    return _to_list(await env.cms.prepare(GET_ALBUM_ENTRY).bind(album_id).all())


async def get_by_tag(env, tag_id):
    return _to_list(await env.cms.prepare(GET_BY_TAG).bind(tag_id).all())


async def slug_exists(env, slug):
    row = await env.cms.prepare(SLUG_EXISTS).bind(slug).first()
    return row is not None


# --- Escrituras -------------------------------------------------------------

async def _resolve_album_id(env, album_name):
    if not album_name:
        return None
    await env.cms.prepare(CREATE_ALBUM).bind(album_name).run()
    row = _to_dict(await env.cms.prepare(GET_ALBUM_ID).bind(album_name).first())
    return row["id"]


async def create_entry(env, entry_data):
    db = env.cms

    # Insert en tags y obtener tag ids
    tags_ids = []
    for tag_name in entry_data.get("tags", []):
        await db.prepare(CREATE_TAG).bind(tag_name).run()
        row = _to_dict(await db.prepare(GET_TAG_ID).bind(tag_name).first())
        tags_ids.append(row["id"])

    # Insert en album y obtener album id
    album_id = await _resolve_album_id(env, entry_data.get("album"))

    # Insert en entry
    res = await db.prepare(CREATE_ENTRY).bind(
        entry_data["type"],
        entry_data["title"],
        entry_data["description"],
        entry_data["body"],
        entry_data["slug"],
        entry_data["file_path"],
        entry_data["file_size"],
        entry_data["width"],
        entry_data["height"],
        entry_data["taken_at"],
        entry_data["is_analog"],
        entry_data["camera_model"],
        entry_data["film_stock"],
        entry_data["duration"],
        album_id,
    ).run()
    entry_id = res.meta.last_row_id

    # Conectar entry con tag
    for tag_id in tags_ids:
        await db.prepare(CREATE_ENTRY_TAG).bind(tag_id, entry_id).run()

    return entry_id


async def update_entry(env, entry_id, entry_data):
    db = env.cms

    album_id = await _resolve_album_id(env, entry_data.get("album"))

    # Preservar estado y fecha de publicacion existentes (el form no los envia).
    current = _to_dict(await db.prepare(GET_DETAIL).bind(entry_id).first())

    await db.prepare(UPDATE_ENTRY).bind(
        entry_data["type"],
        entry_data["title"],
        entry_data["description"],
        entry_data["body"],
        entry_data["slug"],
        entry_data["file_path"],
        entry_data["file_size"],
        entry_data["width"],
        entry_data["height"],
        entry_data["taken_at"],
        entry_data["is_analog"],
        entry_data["camera_model"],
        entry_data["film_stock"],
        entry_data["duration"],
        album_id,
        current["status"],
        current["published_at"],
        entry_id,
    ).run()
    await db.prepare(DELETE_ORPHAN_ALBUMS).run()
    await db.prepare(DELETE_ORPHAN_TAGS).run()


async def publish_bulk(env, ids):
    for entry_id in ids:
        await env.cms.prepare(PUBLISH_ENTRY).bind(entry_id).run()
    return len(ids)


async def draft_bulk(env, ids):
    for entry_id in ids:
        await env.cms.prepare(DRAFT_ENTRY).bind(entry_id).run()
    return len(ids)


async def delete_bulk(env, ids):
    for entry_id in ids:
        await env.cms.prepare(DELETE_ENTRY).bind(entry_id).run()
    await env.cms.prepare(DELETE_ORPHAN_ALBUMS).run()
    await env.cms.prepare(DELETE_ORPHAN_TAGS).run()
    return len(ids)
