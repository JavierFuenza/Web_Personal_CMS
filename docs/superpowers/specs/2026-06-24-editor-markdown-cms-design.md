# Editor markdown (EasyMDE) para `body` en el CMS

Fecha: 2026-06-24

## Objetivo

Reemplazar el `<textarea name="body">` plano del CMS por un editor markdown
EasyMDE (toolbar + preview en vivo) en los formularios de crear (`/form`) y
editar (`/editar/{id}`). El contenido se sigue guardando como markdown plano;
el blog lo renderiza con mistune como hoy.

## Decisiones acordadas

- Editor: **EasyMDE** (librería lista, empaqueta CodeMirror).
- Assets **self-hosted** (vendored en el repo, servidos por Workers Assets), sin
  CDN en runtime. Incluye los iconos (FontAwesome) vendoreados para no depender
  de red externa (`autoDownloadFontAwesome: false`).
- Aplica a `body` en **FORM y EDIT**.
- Cero cambios de backend / db / formato de guardado: EasyMDE sincroniza con el
  `<textarea>` subyacente, así que el POST manda `body` igual que ahora.

## Arquitectura

### Assets (Workers Assets, no bundle del Worker)

- Vendorear en `public/static/`: `easymde.min.js`, `easymde.min.css`, y los
  assets de iconos que EasyMDE/FontAwesome necesite (fuente/css), de modo que el
  editor cargue 100% desde `/static/...` sin CDN.
- Copia de referencia idéntica en `static/` (convención del repo, igual que
  `form.js` y `panel.js`).
- Importante: Workers Assets sirve estos archivos como estáticos; **no** cuentan
  para el límite de tamaño del Python Worker (a diferencia de dependencias
  Python como Pillow, que sí se quitaron por tamaño).

### Inicialización (`public/static/cms-editor.js`, nuevo)

- Script propio que, si existe `#body` en la página, hace
  `new EasyMDE({ element: document.getElementById("body"), ... })`.
- Config: toolbar por defecto (negrita, itálica, título, cita, listas, link,
  código, preview, fullscreen), `spellChecker: false` (evita corrector inglés
  sobre español), `autoDownloadFontAwesome: false`, `status` mínimo.
- Copia de referencia idéntica en `static/cms-editor.js`.

### Plantillas (`src/views.py`, strings embebidas)

- En `FORM` y `EDIT`: agregar en `<head>`
  `<link rel="stylesheet" href="/static/easymde.min.css">`, y antes de cerrar
  `<body>` (después del textarea) `<script src="/static/easymde.min.js">` seguido
  de `<script src="/static/cms-editor.js">`.
- El `<textarea id="body" name="body">` se mantiene tal cual; EasyMDE lo
  reemplaza visualmente y lo mantiene sincronizado.
- En FORM, `cms-editor.js` convive con `form.js` (subida a R2); EasyMDE se monta
  sobre `body` aunque el tipo sea foto/video (ahí `body` no se usa) — más simple
  que condicionar por tipo.

## Flujo de datos

Usuario escribe en EasyMDE → EasyMDE sincroniza el `<textarea name="body">` →
submit del form → `POST /form` o `/editar/{id}` recibe `body` como markdown
plano (sin cambios) → se guarda en D1 → el blog lo renderiza con mistune.

## Manejo de errores

- Si EasyMDE no carga (asset faltante), el `<textarea>` plano queda funcional
  (degradación natural: el form sigue enviando `body`).
- `cms-editor.js` chequea que `#body` exista antes de inicializar (en páginas
  sin ese campo no hace nada).

## Fuera de alcance (YAGNI)

- Solo el campo `body`. Title/description/tags siguen como inputs normales.
- Sin subida de imágenes desde el editor (el flujo R2 ya existe aparte).
- El preview de EasyMDE usa su parser (marked), no mistune → puede diferir un
  poco del render real del blog. Aceptable; el render canónico sigue en el blog.
- Sin cambios en API ni en el sitio estático ni en el blog.

## Verificación

Sin suite ni linter en el CMS. Verificación manual con `uv run pywrangler dev`
(o `.venv/bin/python -m pywrangler dev` si el shebang del venv falla):
- `/form`: el editor aparece sobre `body`, toolbar y preview funcionan, los
  iconos cargan sin red externa.
- Crear un post escribiendo markdown con el editor; confirmar que se guarda y
  que el blog lo renderiza correctamente.
- `/editar/{id}` de un post existente: el editor carga el `body` actual y al
  guardar conserva el markdown.
