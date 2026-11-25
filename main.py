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
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory="templates")

def subir_archivo_a_storage(data_url: str, carpeta: str) -> str | None:
    if not data_url:
        return None
    if data_url.startswith("https://"):
        return data_url

    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    supabase_key = os.getenv("SUPABASE_KEY", "")

    if not (data_url.startswith("data:") and ";base64," in data_url):
        return None

    try:
        encabezado, b64_data = data_url.split(";base64,", 1)
        mime = encabezado.replace("data:", "").strip().lower()
        permitidos = {
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
            "application/pdf": "pdf"
        }
        if mime not in permitidos:
            return None

        raw_bytes = base64.b64decode(b64_data)
        if len(raw_bytes) > 6 * 1024 * 1024:
            return None

        if supabase_url and supabase_key:
            ext = permitidos[mime]
            nombre_archivo = f"{carpeta}/{uuid.uuid4().hex}.{ext}"
            endpoint = f"{supabase_url}/storage/v1/object/fotos-autostock/{nombre_archivo}"

            req = urllib.request.Request(endpoint, data=raw_bytes, method="POST")
            req.add_header("Authorization", f"Bearer {supabase_key}")
            req.add_header("apikey", supabase_key)
            req.add_header("Content-Type", mime)

            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status in (200, 201):
                    return f"{supabase_url}/storage/v1/object/public/fotos-autostock/{nombre_archivo}"
    except Exception as e:
        print(f"[STORAGE ERROR] No se pudo subir archivo: {e}")

    if data_url.startswith("data:image/") and len(data_url) < 450_000:
        return data_url
    return None
@app.get("/", response_class=HTMLResponse)
@app.get("/mostrador", response_class=HTMLResponse)
def vista_mostrador(request: Request):
    import database
    import models
    import security
    import seed

    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        ahora = ahora_utc()

        rol_str = (usuario.rol.value if hasattr(usuario.rol, "value") else str(usuario.rol)) if usuario else "Publico"
        es_admin = (rol_str == "Administrador")
        es_vendedor = (rol_str == "Vendedor")
        es_mecanico = (rol_str == "Mecanico")
        es_operador = (es_admin or es_vendedor)

        todos_usuarios = db.query(models.Usuario).all()
        usuarios_map = {u.id: u for u in todos_usuarios}
        usuarios_admin_lista = todos_usuarios if es_admin else []

        bitacora_lista = []
        procedencias_map = {}
        if es_admin:
            regs_bitacora = db.query(models.BitacoraAuditoria).order_by(models.BitacoraAuditoria.id.desc()).limit(150).all()
            for b in regs_bitacora:
                u_b = usuarios_map.get(b.usuario_id)
                bitacora_lista.append({
                    "id": b.id,
                    "usuario": u_b.nombre if u_b else "Sistema",
                    "accion": b.accion_realizada,
                    "fecha": formatear_cancun(b.fecha_hora)
                })
                if b.accion_realizada.startswith("[PROCEDENCIA #"):
                    try:
                        cabecera, resto = b.accion_realizada.split("]", 1)
                        pid = int(cabecera.replace("[PROCEDENCIA #", "").strip())
                        if pid not in procedencias_map:
                            nota_p, url_p = (resto.split("| URL:", 1) + [""])[:2]
                            procedencias_map[pid] = {"nota": nota_p.strip(), "url": url_p.strip()}
                    except Exception:
                        pass

        strikes_regs = db.query(models.BitacoraAuditoria).filter(
            models.BitacoraAuditoria.accion_realizada == "INCUMPLIMIENTO_SUBASTA"
        ).all()
        strikes_map = {}
        for st in strikes_regs:
            strikes_map[st.usuario_id] = strikes_map.get(st.usuario_id, 0) + 1
        
def subir_fotos_a_storage(url_imagen_raw: str | None, carpeta: str, limite: int) -> list[str]:
    if not url_imagen_raw:
        return []
    try:
        lista_items = json.loads(url_imagen_raw) if url_imagen_raw.startswith("[") else [url_imagen_raw]
    except Exception:
        lista_items = [url_imagen_raw]

    urls_finales = []
    for item in lista_items[:limite]:
        if not item:
            continue
        url_subida = subir_archivo_a_storage(str(item), carpeta)
        if url_subida:
            urls_finales.append(url_subida)
    return urls_finales

async def enviar_alerta_whatsapp_task(telefono: str, producto_id: int, nombre_pieza: str):
    print(f"[NOTIFICACION] Afiliado ({telefono}): Refacción #{producto_id} ({nombre_pieza}) vendida.")
        
