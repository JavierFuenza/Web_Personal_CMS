"""Plantillas HTML embebidas.

En Workers no hay filesystem en runtime, asi que las plantillas no se leen
desde templates/*.html (eso rompe Jinja2 FileSystemLoader). Se cargan como
strings via DictLoader. Los .html en templates/ quedan como referencia.
"""

PANEL = """<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CMS</title>
    <style>
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 1rem;
        }

        .card {
            border: 1px solid #ccc;
            padding: 1rem;
            overflow: hidden;
            word-break: break-word;
        }

        .card.selected {
            border-color: #333;
            background: #f3f3f3;
        }

        .card p {
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        /* Barra de acciones masivas: fija abajo para alcance con el pulgar en movil. */
        #bulk-bar {
            position: fixed;
            left: 0;
            right: 0;
            bottom: 0;
            display: none;
            gap: .5rem;
            align-items: center;
            flex-wrap: wrap;
            padding: .75rem 1rem;
            background: #fff;
            border-top: 1px solid #ccc;
        }

        #bulk-bar.visible { display: flex; }
        #bulk-bar button { padding: .5rem .9rem; }
        #bulk-count { margin-right: auto; }

        /* Modal de confirmacion de borrado. */
        #modal-overlay {
            position: fixed;
            inset: 0;
            display: none;
            align-items: center;
            justify-content: center;
            background: rgba(0, 0, 0, .5);
            padding: 1rem;
        }

        #modal-overlay.visible { display: flex; }

        #modal {
            background: #fff;
            border: 1px solid #333;
            padding: 1.5rem;
            max-width: 360px;
            width: 100%;
        }

        #modal .actions {
            display: flex;
            gap: .5rem;
            justify-content: flex-end;
            margin-top: 1rem;
        }
    </style>
</head>

<body>
    <h1>PANEL CMS PAGINA WEB</h1>

    {% if request.query_params.get('msg') %}
    <p>{{ request.query_params.get('msg') }}</p>
    {% endif %}

    <a href="/form">CREAR POST</a>

    <br><br>

    <label><input type="checkbox" id="select-all"> Seleccionar todo</label>

    <h2>POSTS</h2>

    <div class="grid">
        {% for entry in entries %}
        <div class="card" data-card="{{ entry['id'] }}">
            <label>
                <input type="checkbox" class="select-entry" data-id="{{ entry['id'] }}">
                Seleccionar
            </label>
            <p>Tipo:{{ entry['type'] }} — Estado:<span data-status="{{ entry['id'] }}">{{ entry['status'] }}</span></p>
            <h3>Titulo:{{ entry['title'] }}</h3>
            <p>Descripcion:{{ entry['description'] }}</p>
            {% if entry['album_name'] %}
            <p>{{ entry['album_name'] }}</p>
            {% endif %}
            <a href="/editar/{{ entry['id'] }}">Editar</a>
            <br><br>
            <button type="button" data-action="publish" data-id="{{ entry['id'] }}">Publicar</button>
            <button type="button" data-action="draft" data-id="{{ entry['id'] }}">Draftear</button>
            <button type="button" data-action="delete" data-id="{{ entry['id'] }}">Eliminar</button>
        </div>
        {% endfor %}
    </div>

    <div id="bulk-bar">
        <span id="bulk-count">0 seleccionadas</span>
        <button type="button" data-bulk="publish">Publicar</button>
        <button type="button" data-bulk="draft">Draftear</button>
        <button type="button" data-bulk="delete">Eliminar</button>
    </div>

    <div id="modal-overlay">
        <div id="modal">
            <p id="modal-text">¿Eliminar?</p>
            <div class="actions">
                <button type="button" id="modal-cancel">Cancelar</button>
                <button type="button" id="modal-confirm">Eliminar</button>
            </div>
        </div>
    </div>

    <script src="/static/panel.js"></script>
</body>

</html>"""

FORM = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Form</title>
</head>
<body>
    <h1>FORMULARIO</h1>
    <a href="/panel">VOLVER</a>

    <!-- Sin enctype multipart: form.js sube los archivos directo a R2 y este
         POST lleva solo texto (incluida la metadata de los archivos subidos). -->
    <form action="/form" method="post">
        <div>
        <h2>Selecciona tipo de entry</h2>
        <label>
            <input type="radio" name="type" id="foto" value="photo"> Foto
        </label>
        <label>
            <input type="radio" name="type" id="post" value="post"> Post
        </label>
        <label>
            <input type="radio" name="type" id="video" value="video"> Video
        </label>
        </div>
        <br>
        <label for="title">Titulo</label>
        <input type="text" name="title" id="title">
        <br> <br>
        <label for="slug">Slug(url)</label>
        <input type="text" name="slug" id="slug">
        <br> <br>
        <label for="description">Descripcion</label>
        <input type="text" name="description" id="description">
        <br> <br>
        <label for="body">Cuerpo</label>
        <br>
        <textarea name="body" id="body" rows="10" cols="50"></textarea>
        <br> <br>
        <label for="file">Fotos o Videos</label>
        <br>
        <!-- Sin name: el archivo lo maneja form.js (subida directa a R2), no se
             envia como parte del POST. -->
        <input type="file" id="file" multiple>
        <br> <br>
        <label for="taken_at">Fecha</label>
        <input type="date" name="taken_at" id="taken_at">
        <label for="album">Album</label>
        <input type="text" name="album" id="album">
        <br> <br>
        <label for="is_analog">Analoga</label>
        <input type="checkbox" name="is_analog" id="is_analog">
        <label for="camera_model">Camara</label>
        <input type="text" name="camera_model" id="camera_model">
        <label for="film_stock">Pelicula</label>
        <input type="text" name="film_stock" id="film_stock">
        <br> <br>
        <label for="tags">Etiquetas</label>
        <input type="text" name="tags" id="tags">
        <br><br>

        <!-- Los inputs que genera form.js (titles/descriptions/photo_tags) van
             aqui dentro, asi se envian junto al resto del formulario. -->
        <div id="batch-cards"></div>
        <br><br>
        <button type="submit">SUBIR</button>
    </form>
    <script src="/static/form.js"></script>
</body>
</html>"""

EDIT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Form</title>
</head>
<body>
    <h1>FORMULARIO</h1>
    <a href="/panel">VOLVER</a>

    <form action="/form" method="post" enctype="multipart/form-data">
        <div>
        <h2>Selecciona tipo de entry</h2>
        <label>
            <input type="radio" name="type" id="foto" value="photo" {% if entry['type'] == 'photo' %}checked{% endif %}> Foto
        </label>
        <label>
            <input type="radio" name="type" id="post" value="post" {% if entry['type'] == 'post'  %}checked{% endif %}> Post
        </label>
        <label>
            <input type="radio" name="type" id="video" value="video" {% if entry['type'] == 'video' %}checked{% endif %}> Video
        </label>
        </div>
        <br>
        <label for="title">Titulo</label>
        <input type="text" name="title" id="title" value="{{ entry['title'] or '' }}">
        <br> <br>
        <label for="slug">Slug(url)</label>
        <input type="text" name="slug" id="slug" value="{{ entry['slug']  or '' }}">
        <br> <br>
        <label for="description">Descripcion</label>
        <input type="text" name="description" id="description" value="{{ entry['description'] or '' }}">
        <br> <br>
        <label for="body">Cuerpo</label>
        <br>
        <textarea name="body" id="body" rows="10" cols="50">{{ entry['body'] or '' }}</textarea>
        <br> <br>
        <label for="taken_at">Fecha</label>
        <input type="date" name="taken_at" id="taken_at" value="{{ entry['taken_at'] or '' }}">
        <label for="album">Album</label>
        <input type="text" name="album" id="album" value="{{ entry['album_name'] or '' }}">
        <br> <br>
        <label for="is_analog">Analoga</label>
        <input type="checkbox" name="is_analog" id="is_analog" {% if entry['is_analog'] %}checked{% endif %}>
        <label for="camera_model">Camara</label>
        <input type="text" name="camera_model" id="camera_model" value="{{ entry['camera_model'] or '' }}">
        <label for="film_stock">Pelicula</label>
        <input type="text" name="film_stock" id="film_stock" value="{{ entry['film_stock']   or '' }}">
        <br> <br>
        <label for="tags">Etiquetas</label>
        <input type="text" name="tags" id="tags" value="{{ tags }}">
        <br><br>
        <button type="submit">SUBIR</button>
    </form>

</body>
</html>"""

TEMPLATES = {
    "panel.html": PANEL,
    "form.html": FORM,
    "edit.html": EDIT,
}
