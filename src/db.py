import sqlite3

DB_path = "db.sqlite3"

# Conexion a db
def get_conn():
    conn = sqlite3.connect(DB_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row  # para acceder por nombre: row["title"]
    return conn

#Configurar db
def init_db():
    with open('sql/schema.sql', 'r') as file:
        schema = file.read()

    conn = get_conn()
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()

# Obtener todos los registros (vistazo) (para galeria)
def get_all():
    with open('sql/get_all.sql', 'r') as file:
        getall = file.read()

    conn = get_conn()
    try:
        return conn.execute(getall).fetchall()
    finally:
        conn.close()

# Obtener lista de tags disponibles
def get_tags():
    with open('sql/get_tags.sql', 'r') as file:
        getags = file.read()

    conn = get_conn()
    try:
        return conn.execute(getags).fetchall()
    finally:
        conn.close()

# Obtener tags asociadas a un entry
def get_entry_tags(entry_id):
    with open('sql/get_entry_tags.sql', 'r') as file:
        getet = file.read()

    conn = get_conn()
    try:
        return conn.execute(getet,(entry_id,)).fetchall()
    finally:
        conn.close()


# Obtener entry por tipo (Retorna vistazo, no todo el detalle)
def get_by_type(entry_type):
    with open('sql/get_by_type.sql', 'r') as file:
        getbt = file.read()

    conn = get_conn()
    try:
        return conn.execute(getbt, (entry_type,)).fetchall()
    finally:
        conn.close()
    
# Obtener detalle
def get_detail(entry_id):
    with open('sql/get_detail.sql', 'r') as file:
        getd = file.read()
    conn = get_conn()
    try:
        entry = conn.execute(getd, (entry_id,)).fetchone()
    finally:
        conn.close()
    tags = get_entry_tags(entry_id)
    return entry, tags

# Obtener entries por estado (publicadas o borradores) (sirve para front y cms)
def get_by_status(entry_status):
    with open('sql/get_by_status.sql', 'r') as file:
        gets = file.read()

    conn = get_conn()
    try:
        return conn.execute(gets,(entry_status,)).fetchall()
    finally:
        conn.close()

# Obtener todos los albums
def get_albums():
    with open('sql/get_albums.sql', 'r') as file:
        geta = file.read()
    
    conn = get_conn()
    try:
        return conn.execute(geta).fetchall()
    finally:
        conn.close()

# Obtener fotos de un album especifico
def get_album_entry(album_id):
    with open('sql/get_album_entry.sql', 'r') as file:
            getae = file.read()

    conn = get_conn()
    try:
        return conn.execute(getae,(album_id,)).fetchall()
    finally:
        conn.close()

# Obtener entry de un tag especifico
def get_by_tag(tag_id):
    with open('sql/get_by_tag.sql', 'r') as file:
        gett = file.read()

    conn = get_conn()
    try:
        return conn.execute(gett,(tag_id,)).fetchall()
    finally:
        conn.close()

# Crear una entry

def create_entry(entry_data):

# entry_data = {
#     "type": "",          # "photo" | "video" | "post"
#     "title": "",
#     "description": "",
#     "body": "",          # solo posts
#     "slug": "",          # solo posts
#     "file_path": "",     # foto y video
#     "file_size": 0,      # foto y video
#     "width": 0,          # solo foto
#     "height": 0,         # solo foto
#     "taken_at": "",      # solo foto
#     "is_analog": 0,      # solo foto, 0 | 1
#     "camera_model": "",  # solo foto
#     "film_stock": "",    # solo foto
#     "duration": 0,       # solo video
#     "album": "",         # nombre del album, foto y video
#     "tags": [],          # lista de strings
# }

    with open('sql/create_tag.sql', 'r') as file:
        create_tag = file.read()
    with open('sql/get_tag_id.sql', 'r') as file:
        getti = file.read()
    with open('sql/create_album.sql', 'r') as file:
        create_album = file.read()
    with open('sql/get_album_id.sql', 'r') as file:
        getai = file.read()
    with open('sql/create_entry.sql', 'r') as file:
        create = file.read()
    with open('sql/create_entry_tag.sql', 'r') as file:
        create_et = file.read()

    conn = get_conn()
    try:
        #Insert en tags y obtener tag ids
        tags_ids = []
        for tag_name in entry_data.get("tags", []):
            conn.execute(create_tag,(tag_name,))
            tag_id = conn.execute(getti,(tag_name,)).fetchone()
            tags_ids.append(tag_id["id"])

        #Insert en album y obtener album id
        album_id = None
        if entry_data.get("album"):
            conn.execute(create_album,(entry_data["album"],))
            album_id = conn.execute(getai,(entry_data["album"],)).fetchone()["id"]
        entry_data["album_id"] = album_id

        #Insert en entry
        cursor = conn.execute(create, entry_data)
        entry_id = cursor.lastrowid

        #Conectar entry con tag
        for tag_id in tags_ids:
            conn.execute(create_et,(tag_id,entry_id))

        conn.commit()
        return entry_id
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()

def update_entry(entry_data): #ATENTO AL DESARROLLAR EL FORM, YA QUE NECESITA TODAS LAS COLUMNAS
    with open('sql/update_entry.sql', 'r') as file:
            updt = file.read()

    conn = get_conn()
    try:
        conn.execute(updt,entry_data)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()
    
def delete_entry(entry_id):
    with open('sql/delete_entry.sql', 'r') as file:
        delete = file.read()

    conn = get_conn()
    try:
        conn.execute(delete,(entry_id,))
        conn.commit()
    finally:
        conn.close()

def publish_entry(entry_id):
    with open('sql/publish_entry.sql', 'r') as file:
            publish = file.read()

    conn = get_conn()
    try:
        conn.execute(publish,(entry_id,))
        conn.commit()
    finally:
        conn.close()

def draft_entry(entry_id):
    with open('sql/draft_entry.sql', 'r') as file:
            draft = file.read()

    conn = get_conn()
    try:
        conn.execute(draft,(entry_id,))
        conn.commit()
    finally:
        conn.close()

