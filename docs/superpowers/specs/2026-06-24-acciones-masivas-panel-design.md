# Acciones masivas + modal de confirmación en el panel CMS

Fecha: 2026-06-24

## Objetivo

Permitir en `/panel` seleccionar múltiples entries y aplicarles en bloque
**publicar**, **draftear** o **eliminar**. Al eliminar (individual o masivo)
mostrar un modal de confirmación. Mantener el estilo actual del panel y que la
página siga siendo responsive (uso desde el teléfono para subir fotos).

## Decisiones acordadas

- Interacción vía **JS + `fetch`**, sin recargar la página.
- Se **mantienen** los botones individuales por tarjeta (Publicar/Draftear/
  Eliminar) Y se agrega selección por checkboxes + barra de acciones masivas.
- El modal de confirmación aparece **solo al eliminar** (individual o masivo).
  Publicar/draftear se ejecutan directo.
- Tras publicar/draftear: la tarjeta actualiza su texto `Estado:` in-place.
  Tras eliminar: la tarjeta se quita del DOM.
- Mobile-first / responsive: barra de acciones y modal usables en pantalla de
  teléfono.

## Backend

### Endpoint nuevo (`main.py`)

`POST /entries/bulk` — body JSON:

```json
{ "action": "publish" | "draft" | "delete", "ids": [1, 2, 3] }
```

Respuesta JSON: `{ "ok": true, "count": <n> }`. Valida que `action` sea una de
las tres y que `ids` sea lista de enteros; si no, `{ "ok": false }` con 400.

Reemplaza las 3 rutas single actuales (`POST /publish/{id}`, `POST /draft/{id}`,
`POST /delete/{id}`) y sus `RedirectResponse`. El caso "un botón de tarjeta" es
un bulk con un solo id. Se elimina el código muerto resultante.

### `db.py`

Nuevas funciones que operan sobre una lista de ids:

- `publish_bulk(env, ids)` — marca `published` + `published_at` para cada id.
- `draft_bulk(env, ids)` — marca `draft` para cada id.
- `delete_bulk(env, ids)` — por cada id: borra el objeto R2 si `file_path`
  existe (reusando la lógica actual de `main.delete`: no bloquear si R2 falla),
  luego borra la fila. Al final corre una vez `DELETE_ORPHAN_ALBUMS` y
  `DELETE_ORPHAN_TAGS`.

D1 no tiene transacciones multi-statement con rollback → se mantiene el patrón
compensatorio actual (borrar R2 antes de la fila para no dejar huérfanos). Se
itera id por id con `?` posicional; no se construye `IN (...)` dinámico para no
complicar el binding posicional.

Se eliminan las funciones single `publish_entry`, `draft_entry`, `delete_entry`
(absorbidas por las bulk). La limpieza de R2 que hoy vive en el handler
`main.delete` se mueve a `delete_bulk`.

## Frontend

### `views.py` — plantilla PANEL

- Checkbox por tarjeta con `data-id="{{ entry['id'] }}"`.
- Checkbox "seleccionar todo" en la cabecera de la lista.
- Barra de acciones (oculta hasta tener ≥1 seleccionado) con contador
  "N seleccionadas" y botones **Publicar / Draftear / Eliminar**.
- Botones individuales por tarjeta se conservan; pasan a ser `<button>` con
  `data-id` y `data-action` (ya no `<form>` que postea).
- El texto de estado de la tarjeta se envuelve en un span identificable
  (`data-status` / clase) para poder actualizarlo in-place.
- Modal de confirmación: overlay en HTML embebido, oculto por defecto, con
  título "Eliminar N entrada(s)" y botones Cancelar / Confirmar.
- CSS embebido en la plantilla (como ya está): se agregan estilos para barra de
  acciones, modal/overlay y checkboxes, manteniendo la paleta y el look actual.
  Reglas responsive (barra fija abajo o apilada en pantallas chicas, modal con
  `max-width` y centrado) para uso en teléfono.

### `public/static/panel.js` (nuevo)

Mismo patrón que `form.js` (servido por Workers Assets en `/static/panel.js`,
referenciado al final de la plantilla PANEL). Responsabilidades:

- Mantener el set de ids seleccionados según los checkboxes; sincronizar el
  "seleccionar todo" y mostrar/ocultar la barra + contador.
- Disparar acciones (de la barra o de un botón de tarjeta) con un solo helper
  que hace `fetch('POST /entries/bulk', { action, ids })`.
- Para `delete`: abrir el modal primero; confirmar dispara el fetch, cancelar lo
  cierra sin hacer nada.
- Tras respuesta OK: en delete quitar del DOM las tarjetas afectadas; en
  publish/draft actualizar el texto `Estado:` in-place. Manejar error con un
  aviso simple.

> Recordatorio del repo: la plantilla efectiva es la string embebida en
> `views.py` (`DictLoader`), no `templates/*.html`. Para el JS, el archivo que
> sirve Workers Assets es `public/static/panel.js`; mantener `static/panel.js`
> en sync si se versiona igual que `form.js`.

## Flujo de datos

checkbox(es) → ids en JS → click acción → (si delete) modal de confirmación →
`fetch POST /entries/bulk {action, ids}` → JSON `{ok, count}` → update del DOM
(quitar tarjetas en delete / actualizar Estado en publish-draft).

## Manejo de errores

- Endpoint valida `action` e `ids`; entradas inválidas → 400 `{ok:false}`.
- `delete_bulk`: si falla el borrado de R2 de un id, no bloquea el borrado de la
  fila (igual que hoy).
- JS: si `fetch` no es OK, mostrar aviso y no tocar el DOM.

## Fuera de alcance (YAGNI)

- Sin paginación ni filtros nuevos en el panel.
- Sin selección persistente entre recargas.
- Sin confirmación para publicar/draftear.
- Sin cambios en API pública ni en el sitio estático.

## Verificación

No hay test suite ni linter en el repo. Verificación manual con
`uv run pywrangler dev`: crear/seleccionar entries, probar publicar/draftear/
eliminar en bloque e individual, confirmar el modal en delete, y comprobar la
barra + modal en viewport de teléfono.
