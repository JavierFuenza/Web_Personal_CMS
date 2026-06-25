# Acciones masivas + modal de confirmación en el panel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir seleccionar múltiples entries en `/panel` y publicar/draftear/eliminar en bloque, con modal de confirmación al eliminar.

**Architecture:** Endpoint único `POST /entries/bulk` que recibe JSON `{action, ids}` y devuelve JSON. Las funciones bulk en `db.py` iteran id por id (D1 solo acepta `?` posicional, sin transacciones). El panel usa un `panel.js` nuevo (Workers Assets) con checkboxes, barra de acciones y modal; todo vía `fetch` sin recargar.

**Tech Stack:** Cloudflare Python Worker (FastAPI + Jinja2 embebido vía DictLoader), D1 async, R2, JS vanilla servido por Workers Assets.

## Global Constraints

- D1 se accede como `env.cms`; binding R2 `env.cms_media`. (CLAUDE.md)
- D1 es async y solo acepta `?` posicional — nunca `:name`.
- Sin filesystem en runtime: SQL embebido en `db.py`; plantillas embebidas como strings en `views.py` (`DictLoader`). Editar `templates/*.html` o `sql/*.sql` NO cambia runtime.
- D1 devuelve JsProxy: convertir con `_to_dict` / `_to_list` antes de usar.
- Sin transacciones multi-statement con rollback: compensar manualmente (borrar objeto R2 antes de la fila para no dejar huérfanos).
- `file_path` guarda la KEY de R2, no URL.
- El JS efectivo lo sirve Workers Assets desde `public/static/`; `static/` es copia de referencia que se mantiene en sync (igual que `form.js`).
- No hay test suite ni linter en el repo: la verificación es manual con `uv run pywrangler dev`.

---

### Task 1: Backend — funciones bulk en db.py y endpoint /entries/bulk

**Files:**
- Modify: `src/db.py` (añadir `publish_bulk`, `draft_bulk`, `delete_bulk`; eliminar `publish_entry`, `draft_entry`, `delete_entry`)
- Modify: `src/main.py` (añadir `POST /entries/bulk`; eliminar `POST /publish/{id}`, `POST /draft/{id}`, `POST /delete/{id}`)

**Interfaces:**
- Consumes: SQL constantes existentes `PUBLISH_ENTRY`, `DRAFT_ENTRY`, `DELETE_ENTRY`, `DELETE_ORPHAN_ALBUMS`, `DELETE_ORPHAN_TAGS`, `GET_DETAIL`; helper `_to_dict`; módulo `uploads` (`delete_file`).
- Produces:
  - `db.publish_bulk(env, ids: list[int]) -> int` — devuelve cuántos procesó.
  - `db.draft_bulk(env, ids: list[int]) -> int`.
  - `db.delete_bulk(env, ids: list[int]) -> int` — borra R2 + fila por id, luego limpia huérfanos una vez.
  - Endpoint `POST /entries/bulk`, body JSON `{"action": "publish"|"draft"|"delete", "ids": [int]}`, respuesta `{"ok": bool, "count": int}`.

- [ ] **Step 1: Añadir las tres funciones bulk al final de `src/db.py`**

Reusan el SQL single existente en un loop (no se crea SQL nuevo). `delete_bulk` recibe ya resuelta la limpieza de R2 desde `main` (ver paso 2): aquí solo borra filas y huérfanos.

```python
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
```

- [ ] **Step 2: Eliminar las funciones single de `src/db.py`**

Borrar `delete_entry`, `publish_entry`, `draft_entry` (líneas ~300-311). Sus constantes SQL (`DELETE_ENTRY`, `PUBLISH_ENTRY`, `DRAFT_ENTRY`) se mantienen porque las bulk las reusan.

- [ ] **Step 3: Reemplazar los 3 handlers single por el endpoint bulk en `src/main.py`**

Borrar los handlers `publish`, `draft`, `delete` (líneas ~226-249) y poner en su lugar:

```python
@app.post("/entries/bulk")
async def entries_bulk(request: Request):
    env = request.scope["env"]
    data = await request.json()
    action = data.get("action")
    ids = data.get("ids") or []
    ids = [int(i) for i in ids]
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
```

- [ ] **Step 4: Añadir `JSONResponse` al import de fastapi.responses en `src/main.py`**

Cambiar la línea 9:

```python
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
```

- [ ] **Step 5: Verificar import del módulo (chequeo estático rápido)**

Run: `cd "/home/javier/Github/Repos web-personal/Web_Personal_CMS" && python -c "import ast; ast.parse(open('src/db.py').read()); ast.parse(open('src/main.py').read()); print('ok')"`
Expected: imprime `ok` (sin SyntaxError). No se importan los módulos completos porque dependen del runtime de Workers.

- [ ] **Step 6: Verificar manualmente el endpoint con dev server**

Run: `cd "/home/javier/Github/Repos web-personal/Web_Personal_CMS" && uv run pywrangler dev` (en background) y luego:
`curl -s -X POST localhost:8787/entries/bulk -H 'Content-Type: application/json' -d '{"action":"draft","ids":[1]}'`
Expected: `{"ok": true, "count": 1}`. Probar también `{"action":"nope","ids":[1]}` → 400 `{"ok": false}`, y `{"action":"delete","ids":[<id de prueba>]}` → la entry desaparece de `/panel`.

- [ ] **Step 7: Commit**

```bash
cd "/home/javier/Github/Repos web-personal/Web_Personal_CMS"
git add src/db.py src/main.py
git commit -m "feat: endpoint /entries/bulk para publicar/draftear/eliminar en bloque"
```

---

### Task 2: Frontend — checkboxes, barra de acciones, modal y panel.js

**Files:**
- Modify: `src/views.py` (plantilla `PANEL`: checkboxes, barra de acciones, modal, CSS, `<script src="/static/panel.js">`)
- Create: `public/static/panel.js`
- Create: `static/panel.js` (copia de referencia idéntica, igual que `form.js`)

**Interfaces:**
- Consumes: endpoint `POST /entries/bulk` (Task 1) con body `{action, ids}` → `{ok, count}`. Cada tarjeta expone `data-id` con `entry['id']`.
- Produces: UI funcional; no exporta nada a otras tareas.

- [ ] **Step 1: Reescribir la plantilla `PANEL` en `src/views.py`**

Mantener la paleta/estética actual (bordes grises, grid). Añadir: checkbox por tarjeta con `data-id`, checkbox "seleccionar todo", barra de acciones (oculta por defecto), modal overlay (oculto), y reglas CSS responsive. El texto de estado va en un `<span data-status>` para actualizarlo in-place. Los botones por tarjeta pasan de `<form>` a `<button data-id data-action>`.

```python
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
```

- [ ] **Step 2: Crear `public/static/panel.js`**

```javascript
// Acciones masivas del panel: seleccion por checkboxes, barra de acciones y
// modal de confirmacion al eliminar. Todo via fetch a /entries/bulk, sin recargar.

const selected = new Set();
let pendingDelete = null; // ids en espera de confirmacion en el modal

const bar = document.getElementById("bulk-bar");
const count = document.getElementById("bulk-count");
const overlay = document.getElementById("modal-overlay");
const modalText = document.getElementById("modal-text");

function refreshBar() {
  count.textContent = selected.size + " seleccionadas";
  bar.classList.toggle("visible", selected.size > 0);
  document.querySelectorAll(".select-entry").forEach((cb) => {
    const card = document.querySelector(`[data-card="${cb.dataset.id}"]`);
    if (card) card.classList.toggle("selected", cb.checked);
  });
}

async function runBulk(action, ids) {
  if (!ids.length) return;
  let res;
  try {
    res = await fetch("/entries/bulk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, ids }),
    });
  } catch (e) {
    alert("Error de red");
    return;
  }
  if (!res.ok) {
    alert("La accion fallo");
    return;
  }
  if (action === "delete") {
    ids.forEach((id) => {
      const card = document.querySelector(`[data-card="${id}"]`);
      if (card) card.remove();
      selected.delete(String(id));
    });
  } else {
    const status = action === "publish" ? "published" : "draft";
    ids.forEach((id) => {
      const span = document.querySelector(`[data-status="${id}"]`);
      if (span) span.textContent = status;
    });
  }
  refreshBar();
}

function askDelete(ids) {
  pendingDelete = ids;
  modalText.textContent = "Eliminar " + ids.length + " entrada(s)";
  overlay.classList.add("visible");
}

// Checkboxes por tarjeta.
document.querySelectorAll(".select-entry").forEach((cb) => {
  cb.addEventListener("change", () => {
    if (cb.checked) selected.add(cb.dataset.id);
    else selected.delete(cb.dataset.id);
    refreshBar();
  });
});

// Seleccionar todo.
document.getElementById("select-all").addEventListener("change", (e) => {
  document.querySelectorAll(".select-entry").forEach((cb) => {
    cb.checked = e.target.checked;
    if (cb.checked) selected.add(cb.dataset.id);
    else selected.delete(cb.dataset.id);
  });
  refreshBar();
});

// Botones por tarjeta (action de 1 id).
document.querySelectorAll(".card button[data-action]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const id = btn.dataset.id;
    if (btn.dataset.action === "delete") askDelete([id]);
    else runBulk(btn.dataset.action, [id]);
  });
});

// Barra de acciones masivas.
document.querySelectorAll("#bulk-bar button[data-bulk]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const ids = [...selected];
    if (!ids.length) return;
    if (btn.dataset.bulk === "delete") askDelete(ids);
    else runBulk(btn.dataset.bulk, ids);
  });
});

// Modal.
document.getElementById("modal-cancel").addEventListener("click", () => {
  pendingDelete = null;
  overlay.classList.remove("visible");
});
document.getElementById("modal-confirm").addEventListener("click", () => {
  const ids = pendingDelete || [];
  overlay.classList.remove("visible");
  pendingDelete = null;
  runBulk("delete", ids);
});
```

- [ ] **Step 3: Copiar el JS a la copia de referencia `static/panel.js`**

Run: `cd "/home/javier/Github/Repos web-personal/Web_Personal_CMS" && cp public/static/panel.js static/panel.js`
Expected: ambos archivos idénticos (mismo patrón que `form.js`).

- [ ] **Step 4: Verificar sintaxis de la plantilla embebida**

Run: `cd "/home/javier/Github/Repos web-personal/Web_Personal_CMS" && python -c "import ast; ast.parse(open('src/views.py').read()); print('ok')"`
Expected: imprime `ok`.

- [ ] **Step 5: Verificar manualmente en el dev server**

Run: `cd "/home/javier/Github/Repos web-personal/Web_Personal_CMS" && uv run pywrangler dev` y abrir `localhost:8787/panel`. Comprobar:
- Marcar varias casillas → aparece la barra con el contador; "Seleccionar todo" marca/desmarca todo.
- Publicar/Draftear (barra o tarjeta) cambia el texto `Estado:` sin recargar.
- Eliminar (barra o tarjeta) abre el modal; Cancelar no hace nada; Confirmar quita la(s) tarjeta(s).
- En viewport de teléfono (DevTools responsive ~375px): la barra fija abajo y el modal se ven y se usan bien.

- [ ] **Step 6: Commit**

```bash
cd "/home/javier/Github/Repos web-personal/Web_Personal_CMS"
git add src/views.py public/static/panel.js static/panel.js
git commit -m "feat: seleccion masiva, acciones y modal de borrado en el panel"
```

---

## Notas de verificación final

- No hay tests automatizados: la prueba de aceptación es el recorrido manual de los Steps 6 (Task 1) y 5 (Task 2) en `pywrangler dev`, incluyendo el viewport de teléfono.
- Confirmar que ya no quedan referencias a las rutas viejas: `grep -rn "/publish/\|/draft/\|/delete/" src/` no debe devolver handlers (solo, si acaso, comentarios).
