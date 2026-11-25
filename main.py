import base64
import io
import json
import os
import re
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from sqlalchemy.orm import Session

app = FastAPI(title="AutoStock Mayab")

TZ_CANCUN = ZoneInfo("America/Cancun")
WHATSAPP_MOSTRADOR = re.sub(r"\D", "", os.getenv("WHATSAPP_MOSTRADOR", "529980000000"))

def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)

def a_utc_aware(dt: datetime | None) -> datetime | None:
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def formatear_cancun(dt: datetime | None, fmt: str = "%d/%m/%Y %H:%M") -> str:
    aware = a_utc_aware(dt)
    if not aware:
        return "Reciente"
    return aware.astimezone(TZ_CANCUN).strftime(fmt)

@app.middleware("http")
async def agregar_cabeceras_seguridad(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

@app.get("/static/manifest.json")
def get_manifest():
    ruta = os.path.join(os.path.dirname(__file__), "static", "manifest.json")
    if os.path.exists(ruta):
        return FileResponse(ruta, media_type="application/json")
    return JSONResponse({
        "name": "AutoStock Mayab",
        "short_name": "AutoStock",
        "start_url": "/mostrador",
        "display": "standalone",
        "background_color": "#0f172a",
        "theme_color": "#0f172a"
    })

@app.get("/static/sw.js")
def get_serviceworker():
    ruta = os.path.join(os.path.dirname(__file__), "static", "sw.js")
    if os.path.exists(ruta):
        return FileResponse(ruta, media_type="application/javascript")
    return HTMLResponse("self.addEventListener('fetch', () => {});", media_type="application/javascript")

@app.on_event("startup")
def on_startup():
    import database
    import models
    import seed

    models.Base.metadata.create_all(bind=database.engine)
    db = next(database.get_db())
    try:
        seed.seed_database(db)
    finally:
        db.close()
