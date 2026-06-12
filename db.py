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

'''
Álbumes

get_albums() — listar todos los álbumes
get_entries_by_album(album_id) — fotos de un álbum específico

Búsqueda/filtros

get_by_tag(tag_id) — entradas de un tag específico

'''
'''
create_entry()
update_entry(id)
delete_entry(id)
create_tag(name)
create_album(name)
'''
