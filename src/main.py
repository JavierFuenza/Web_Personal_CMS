# from flask import Flask, flash, redirect, render_template, request, url_for
from src import db
import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

@app.get("/init")
async def init():
    db.init_db()
    return {"status": "ok"}

@app.get("/panel",response_class=HTMLResponse)
async def panel(request: Request):
    context = {
        "entries" : db.get_all()
    }
    return templates.TemplateResponse(name='panel.html', context=context, request=request)

@app.get("/form",response_class=HTMLResponse)
async def form_get(request: Request):
    return templates.TemplateResponse(name="form.html",request=request)

@app.post("/form")
async def form_post(
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
        "tags":         [t.strip() for t in tags.split(',') if t.strip()],
        "file_path":    None,
        "file_size":    None,
        "width":        None,
        "height":       None,
        "duration":     None,
    }
    try:
        db.create_entry(entry_data)
        return RedirectResponse(url="/panel?msg=Entrada_creada_correctamente", status_code=303)
    except Exception as e:
        return RedirectResponse(url="/panel?msg=Error", status_code=303)

@app.post("/publish/{entry_id}")
async def publish(entry_id: int):
    db.publish_entry(entry_id)
    return RedirectResponse(url="/panel", status_code=303)

@app.post("/draft/{entry_id}")
async def draft(entry_id: int):
    db.draft_entry(entry_id)
    return RedirectResponse(url="/panel", status_code=303)

@app.post("/delete/{entry_id}")
async def delete(entry_id: int):
    db.delete_entry(entry_id)
    return RedirectResponse(url="/panel", status_code=303)

@app.get("/editar/{entry_id}", response_class=HTMLResponse)
async def edit_get(request: Request, entry_id: int):
    entry, tags = db.get_detail(entry_id)
    context = {
        "entry": entry,
        "tags": ", ".join([t["tag_name"] for t in tags])
    }
    return templates.TemplateResponse(request=request, name="edit.html", context=context)

@app.post("/editar/{entry_id}")
async def edit_post(
    entry_id: int,
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
    entry, _ = db.get_detail(entry_id)

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
        "tags":         [t.strip() for t in tags.split(',') if t.strip()],
        "file_path":    entry["file_path"],
        "file_size":    entry["file_size"],
        "width":        entry["width"],
        "height":       entry["height"],
        "duration":     entry["duration"],
    }
    db.update_entry(entry_data)
    return RedirectResponse(url="/panel", status_code=303)


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)