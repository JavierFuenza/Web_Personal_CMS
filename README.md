# Web_Personal_CMS

Un CMS para manejar los contenidos de mi pagina web.

Corre sobre **Cloudflare Workers (Python)** + **D1** (SQLite gestionado).
FastAPI se ejecuta sobre el servidor ASGI que provee el runtime de Workers.

## Setup

```bash
# 1. Crear la base D1 y copiar el database_id a wrangler.toml
npx wrangler d1 create cms

# 2. Aplicar el esquema
npx wrangler d1 execute cms --file=./sql/schema.sql

# 3. Dev local (Pyodide + D1 local via miniflare)
uv run pywrangler dev

# 4. Desplegar
uv run pywrangler deploy
```

Tras desplegar, `GET /init` tambien crea las tablas (idempotente). Panel en `/panel`.

## Notas de la migracion a Workers

- `db.py` usa el binding **async** `env.DB` (D1). El SQL va embebido (no hay
  filesystem en runtime). Parametros **posicionales** `?` (D1 no soporta `:nombre`).
- `main.py` expone `Default(WorkerEntrypoint)` y delega en FastAPI via `asgi.fetch`.
  El `env` se obtiene de `request.scope["env"]`.
- Las escrituras en D1 se auto-confirman por sentencia: `create_entry` ya no es
  una transaccion atomica con rollback como en SQLite local.
- Subida de archivos: `POST /form` sube a R2 (binding `BUCKET`) y guarda la key
  en `file_path`. Soporta single y batch (multiples archivos con metadata propia).
  Dimensiones de imagen via Pillow; `duration` de video queda NULL.
  Pendiente: URL publica del bucket y mostrar las imagenes en el panel.
