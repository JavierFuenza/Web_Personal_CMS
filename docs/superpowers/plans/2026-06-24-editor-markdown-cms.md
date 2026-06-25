# Editor markdown (EasyMDE) para `body` en el CMS — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar el `<textarea name="body">` plano del CMS por un editor EasyMDE (toolbar + preview) en `/form` y `/editar/{id}`, sin cambiar cómo se guarda el markdown.

**Architecture:** EasyMDE (vendored, self-host) servido por Workers Assets desde `public/static/`. Un `cms-editor.js` inicializa EasyMDE sobre el `<textarea id="body">` existente; EasyMDE sincroniza el textarea subyacente, así que el POST y el backend no cambian. Iconos de FontAwesome 4.7.0 vendoreados (solo woff2 local), sin CDN.

**Tech Stack:** Cloudflare Python Worker (FastAPI + Jinja2 embebido), Workers Assets, EasyMDE 2.21.0, FontAwesome 4.7.0 (woff2), JS vanilla.

## Global Constraints

- No filesystem en runtime: la plantilla efectiva es la string embebida en `src/views.py` (DictLoader); editar `templates/*.html` NO cambia runtime.
- Assets estáticos los sirve Workers Assets desde `public/` (`[assets] directory = "public"` en `wrangler.toml`): `public/static/x` → `/static/x`. Estos archivos NO cuentan para el límite de tamaño del Python Worker.
- Cero cambios en backend/db/formato: EasyMDE sincroniza el `<textarea name="body">`; el form sigue enviando `body` como markdown plano.
- `autoDownloadFontAwesome: false` (no bajar FA de CDN). Iconos desde woff2 local.
- No hay test suite ni linter en el CMS: verificación = checks de archivos/`ast.parse` + smoke con `pywrangler dev`. Si `uv run pywrangler dev` falla por shebang viejo del venv, usar `.venv/bin/python -m pywrangler dev`.
- Decisión deliberada (desvío del spec): NO se crean copias en `static/`. El review final del trabajo previo constató que `static/` es una copia muerta ya divergente (`static/form.js` ≠ `public/static/form.js`) y que Workers sirve solo `public/`. Duplicar ~400KB de binarios ahí no aporta. Todo va solo a `public/static/`.

---

### Task 1: Vendorear EasyMDE + FontAwesome en public/static/

**Files:**
- Create: `public/static/easymde.min.js`
- Create: `public/static/easymde.min.css`
- Create: `public/static/font-awesome.min.css`
- Create: `public/static/fonts/fontawesome-webfont.woff2`

**Interfaces:**
- Produces: los assets servidos en `/static/easymde.min.js`, `/static/easymde.min.css`, `/static/font-awesome.min.css`, `/static/fonts/fontawesome-webfont.woff2`. La FA css referencia la fuente como `fonts/fontawesome-webfont.woff2?v=4.7.0` (relativo → `/static/fonts/...`).

- [ ] **Step 1: Descargar EasyMDE 2.21.0 y la fuente FA**

```bash
cd "/home/javier/Github/Repos web-personal/Web_Personal_CMS"
mkdir -p public/static/fonts
curl -fsSL -o public/static/easymde.min.js  "https://unpkg.com/easymde@2.21.0/dist/easymde.min.js"
curl -fsSL -o public/static/easymde.min.css "https://unpkg.com/easymde@2.21.0/dist/easymde.min.css"
curl -fsSL -o public/static/fonts/fontawesome-webfont.woff2 "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/fonts/fontawesome-webfont.woff2"
curl -fsSL -o /tmp/fa.css "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css"
```

- [ ] **Step 2: Reescribir el @font-face de FA a solo-woff2 local y guardarlo**

El @font-face original lista eot/woff2/woff/ttf/svg con rutas `../fonts/` (que no resuelven bien y generan 404s). Se reemplaza por una sola fuente woff2 con ruta `fonts/...`:

```bash
cd "/home/javier/Github/Repos web-personal/Web_Personal_CMS"
python3 - <<'PY'
import re
css = open("/tmp/fa.css", encoding="utf-8").read()
new_face = ("@font-face{font-family:'FontAwesome';"
            "src:url('fonts/fontawesome-webfont.woff2?v=4.7.0') format('woff2');"
            "font-weight:normal;font-style:normal}")
css, n = re.subn(r"@font-face\{[^}]*\}", new_face, css, count=1)
assert n == 1, f"esperaba 1 @font-face, reemplace {n}"
open("public/static/font-awesome.min.css", "w", encoding="utf-8").write(css)
print("font-awesome.min.css escrito; @font-face reemplazado")
PY
```

Expected: imprime `font-awesome.min.css escrito; @font-face reemplazado`.

- [ ] **Step 3: Verificar que los 4 assets existen y la css quedó bien**

```bash
cd "/home/javier/Github/Repos web-personal/Web_Personal_CMS"
ls -l public/static/easymde.min.js public/static/easymde.min.css public/static/font-awesome.min.css public/static/fonts/fontawesome-webfont.woff2
grep -c "fonts/fontawesome-webfont.woff2?v=4.7.0' format('woff2')" public/static/font-awesome.min.css
grep -c "\.\./fonts/" public/static/font-awesome.min.css
```

Expected: los 4 archivos existen con tamaño > 0 (easymde.min.js ~327KB, woff2 ~77KB); el primer `grep -c` da `1`; el segundo `grep -c` (rutas viejas `../fonts/`) da `0`.

- [ ] **Step 4: Commit**

```bash
cd "/home/javier/Github/Repos web-personal/Web_Personal_CMS"
git add public/static/easymde.min.js public/static/easymde.min.css public/static/font-awesome.min.css public/static/fonts/fontawesome-webfont.woff2
git commit -m "feat: vendorear EasyMDE 2.21.0 + FontAwesome (woff2) en public/static"
```

---

### Task 2: Script de inicialización cms-editor.js

**Files:**
- Create: `public/static/cms-editor.js`

**Interfaces:**
- Consumes: el global `EasyMDE` (de `/static/easymde.min.js`, Task 1) y el elemento `#body` (textarea de las plantillas, Task 3).
- Produces: el asset `/static/cms-editor.js` que monta EasyMDE sobre `#body` si ambos existen.

- [ ] **Step 1: Crear `public/static/cms-editor.js`**

```javascript
// Monta EasyMDE sobre el textarea #body si esta presente. Degrada al textarea
// plano si EasyMDE no cargo. EasyMDE sincroniza el <textarea> subyacente, asi
// que el form sigue enviando `body` como markdown plano (sin cambios de backend).
(function () {
  var el = document.getElementById("body");
  if (!el || typeof EasyMDE === "undefined") return;
  new EasyMDE({
    element: el,
    autoDownloadFontAwesome: false, // FontAwesome se sirve self-host (Task 1)
    spellChecker: false,            // evita corrector ingles sobre texto espanol
    status: ["lines", "words"],
    toolbar: [
      "bold", "italic", "heading", "|",
      "quote", "unordered-list", "ordered-list", "code", "|",
      "link", "preview", "side-by-side", "fullscreen", "|",
      "guide",
    ],
  });
})();
```

- [ ] **Step 2: Verificar que el archivo existe y referencia EasyMDE/#body**

```bash
cd "/home/javier/Github/Repos web-personal/Web_Personal_CMS"
test -s public/static/cms-editor.js && echo "existe"
grep -c "new EasyMDE" public/static/cms-editor.js
grep -c 'getElementById("body")' public/static/cms-editor.js
```

Expected: imprime `existe`; cada `grep -c` da `1`.

- [ ] **Step 3: Commit**

```bash
cd "/home/javier/Github/Repos web-personal/Web_Personal_CMS"
git add public/static/cms-editor.js
git commit -m "feat: cms-editor.js inicializa EasyMDE sobre el textarea body"
```

---

### Task 3: Enganchar el editor en las plantillas FORM y EDIT

**Files:**
- Modify: `src/views.py` (strings embebidas `FORM` y `EDIT`)

**Interfaces:**
- Consumes: assets de Task 1 (`/static/easymde.min.css`, `/static/easymde.min.js`, `/static/font-awesome.min.css`) y el script de Task 2 (`/static/cms-editor.js`). El `<textarea ... id="body" ...>` ya existe en ambas plantillas.

- [ ] **Step 1: En `src/views.py`, agregar las hojas de estilo al `<head>` de FORM**

Buscar en la string `FORM` la línea `<title>Form</title>` (dentro de su `<head>`) y dejar el head así:

```html
    <title>Form</title>
    <link rel="stylesheet" href="/static/font-awesome.min.css">
    <link rel="stylesheet" href="/static/easymde.min.css">
```

- [ ] **Step 2: En `src/views.py`, cargar los scripts del editor en FORM**

En la string `FORM`, la línea actual antes de `</body>` es `<script src="/static/form.js"></script>`. Dejarla así (agregar EasyMDE + el init después de form.js):

```html
    <script src="/static/form.js"></script>
    <script src="/static/easymde.min.js"></script>
    <script src="/static/cms-editor.js"></script>
```

- [ ] **Step 3: En `src/views.py`, agregar las hojas de estilo al `<head>` de EDIT**

Buscar en la string `EDIT` la línea `<title>Form</title>` (su `<head>`) y dejarla así:

```html
    <title>Form</title>
    <link rel="stylesheet" href="/static/font-awesome.min.css">
    <link rel="stylesheet" href="/static/easymde.min.css">
```

- [ ] **Step 4: En `src/views.py`, cargar los scripts del editor en EDIT**

La string `EDIT` no tiene scripts. Justo antes de su `</body>` (después de `</form>`), agregar:

```html
    <script src="/static/easymde.min.js"></script>
    <script src="/static/cms-editor.js"></script>
</body>
```

- [ ] **Step 5: Verificar que `views.py` parsea y referencia los assets**

```bash
cd "/home/javier/Github/Repos web-personal/Web_Personal_CMS"
python3 -c "import ast; ast.parse(open('src/views.py').read()); print('ast ok')"
grep -c "/static/easymde.min.js" src/views.py
grep -c "/static/cms-editor.js" src/views.py
grep -c "/static/easymde.min.css" src/views.py
```

Expected: `ast ok`; cada `grep -c` da `2` (una vez en FORM, otra en EDIT).

- [ ] **Step 6: Smoke con el dev server**

Levantar `.venv/bin/python -m pywrangler dev` (o `uv run pywrangler dev`) y comprobar que los assets y las páginas responden 200:

```bash
for u in /form /static/easymde.min.js /static/easymde.min.css /static/font-awesome.min.css /static/cms-editor.js /static/fonts/fontawesome-webfont.woff2; do
  curl -s -o /dev/null -w "%{http_code} $u\n" "http://localhost:8787$u"
done
```

Expected: `200` en todas. (La verificación visual —que el editor aparece sobre `body`, la toolbar muestra iconos, el preview funciona, y `/editar/{id}` carga el body existente— la hace el humano en el navegador; no hay browser en este entorno.)

- [ ] **Step 7: Commit**

```bash
cd "/home/javier/Github/Repos web-personal/Web_Personal_CMS"
git add src/views.py
git commit -m "feat: montar editor EasyMDE sobre body en form y editar"
```

---

## Notas de verificación final

- Sin tests automatizados: la aceptación es el recorrido manual del Step 6 de Task 3 en `pywrangler dev` + verificación visual del editor en `/form` y `/editar/{id}`, y que un post creado/editado con el editor renderice bien en el blog.
- El preview de EasyMDE usa su propio parser (marked), no mistune; puede diferir un poco del render real del blog. Aceptable (el render canónico sigue en el blog).
- Degradación: si algún asset falla, el `<textarea>` plano sigue funcional y el form sigue enviando `body`.
