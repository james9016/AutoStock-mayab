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
          productos_raw = db.query(models.Producto).filter(models.Producto.cantidad_disponible > 0).order_by(models.Producto.id.desc()).all()
        productos_sanitizados = []
        for prod in productos_raw:
            precio_final = float(prod.precio_sugerido)
            tiene_descuento_taller = False

            if es_mecanico:
                ganancia = float(prod.precio_sugerido) - float(prod.precio_real)
                if ganancia > 0:
                    precio_final = round(float(prod.precio_sugerido) - (ganancia * 0.15), 2)
                    tiene_descuento_taller = True

            f_ing = a_utc_aware(prod.fecha_ingreso)
            dias_almacen = max(0, (ahora - f_ing).days) if f_ing else 0
            f_ap = a_utc_aware(prod.apartado_hasta)
            dueno_obj = usuarios_map.get(prod.dueno_id)
            cat_val = prod.categoria.value if hasattr(prod.categoria, "value") else str(prod.categoria)
            proc_info = procedencias_map.get(prod.id, {"nota": "", "url": ""})

            productos_sanitizados.append({
                "id": prod.id,
                "categoria": cat_val,
                "nombre_refaccion": prod.nombre_refaccion,
                "marca": prod.marca,
                "modelo": prod.modelo,
                "ano_grupo": prod.ano_grupo,
                "compatibilidad": prod.compatibilidad or "",
                "condicion": prod.condicion or "Original Usada - Excelente",
                "cantidad_disponible": prod.cantidad_disponible,
                "dias_almacen": dias_almacen,
                "apartado": bool(f_ap and f_ap > ahora),
                "precio_publico_original": float(prod.precio_sugerido),
                "precio_sugerido": precio_final,
                "tiene_descuento_taller": tiene_descuento_taller,
                "dueno_id": prod.dueno_id,
                "dueno_nombre": dueno_obj.nombre if dueno_obj else "Bodega",
                "precio_real": float(prod.precio_real) if es_operador else None,
                "ubicacion_fisica": prod.ubicacion_fisica if es_operador else "Disponible en Bodega Central",
                "imagenes": [img.url_imagen for img in prod.imagenes] if prod.imagenes else [],
                "imagenes_objs": [{"id": img.id, "url": img.url_imagen} for img in prod.imagenes] if es_admin else [],
                "procedencia_nota": proc_info["nota"] if es_admin else "",
                "procedencia_url": proc_info["url"] if es_admin else ""
            })

        solicitudes_ids = []
        if es_admin:
            regs = db.query(models.BitacoraAuditoria).filter(
                models.BitacoraAuditoria.accion_realizada == "SOLICITUD_VERIFICACION_ESPECIAL"
            ).all()
            solicitudes_ids = [r.usuario_id for r in regs]

        anuncios_raw = db.query(models.AnuncioMercado).order_by(models.AnuncioMercado.id.desc()).limit(60).all()
        anuncios_mercado = []
        for a in anuncios_raw:
            autor = usuarios_map.get(a.usuario_id)
            ganador = usuarios_map.get(a.ganador_id) if a.ganador_id else None
            cat_texto = a.categoria.value if hasattr(a.categoria, "value") else str(a.categoria)
            rol_autor = (autor.rol.value if hasattr(autor.rol, "value") else str(autor.rol)) if autor else "Publico_General"

            fotos_anuncio = []
            if a.url_imagen:
                if a.url_imagen.startswith("["):
                    try:
                        fotos_anuncio = json.loads(a.url_imagen)
                    except Exception:
                        fotos_anuncio = [a.url_imagen]
                else:
                    fotos_anuncio = [a.url_imagen]
                    fin_sub = a_utc_aware(a.subasta_fin)
            subasta_expirada = bool(a.es_subasta and fin_sub and fin_sub <= ahora)

            historial_pujas = []
            if a.es_subasta:
                pujas_ordenadas = sorted(a.pujas, key=lambda x: x.monto, reverse=True)[:5]
                for pj in pujas_ordenadas:
                    u_pj = usuarios_map.get(pj.usuario_id)
                    historial_pujas.append({
                        "usuario_id": pj.usuario_id,
                        "nombre": u_pj.nombre if u_pj else "Postor",
                        "monto": float(pj.monto),
                        "strikes": strikes_map.get(pj.usuario_id, 0),
                        "hora": formatear_cancun(pj.fecha_puja, "%d/%m %H:%M")
                    })

            anuncios_mercado.append({
                "id": a.id,
                "titulo": a.titulo,
                "categoria": cat_texto,
                "precio": float(a.precio or 0),
                "imagenes": fotos_anuncio,
                "descripcion": a.descripcion,
                "zona_cancun": a.zona_cancun,
                "vendido": bool(a.vendido),
                "es_subasta": bool(a.es_subasta),
                "subasta_fin": fin_sub.isoformat() if fin_sub else None,
                "subasta_expirada": subasta_expirada,
                "puja_actual": float(a.puja_actual or a.precio or 0),
                "ganador_id": a.ganador_id,
                "ganador_nombre": ganador.nombre if ganador else None,
                "ganador_telefono": (ganador.telefono_celular if (ganador and usuario and (usuario.id == a.usuario_id or es_admin)) else ""),
                "historial_pujas": historial_pujas,
                "usuario_id": a.usuario_id,
                "autor_nombre": autor.nombre if autor else "Usuario Cancún",
                "autor_telefono": (autor.telefono_celular if (autor and usuario) else ""),
                "autor_rol": rol_autor,
                "fecha": formatear_cancun(a.fecha_publicacion, "%d/%m/%Y")
            })

        liquidaciones_pendientes = {}
        ventas_detalle = []
        mis_ventas_socio = []
        resumen_caja_hoy = {"efectivo": 0.0, "transferencia": 0.0, "total": 0.0}
        hoy_cancun_str = ahora.astimezone(TZ_CANCUN).strftime("%d/%m/%Y")

        if es_operador:
            pendientes_raw = db.query(models.HistorialVenta).filter(models.HistorialVenta.liquidado_al_dueno == False).all()
            prods_todos_map = {p.id: p for p in db.query(models.Producto).all()}

            for v in pendientes_raw:
                prod = prods_todos_map.get(v.producto_id)
                dueno = usuarios_map.get(prod.dueno_id) if prod else None
                if prod and dueno:
                    if dueno.id not in liquidaciones_pendientes:
                        liquidaciones_pendientes[dueno.id] = {"dueno": dueno.nombre, "saldo": 0.0, "items": []}
                    liquidaciones_pendientes[dueno.id]["saldo"] += float(v.saldo_por_cobrar or 0)
                    liquidaciones_pendientes[dueno.id]["items"].append(v.id)

            ultimas_ventas = db.query(models.HistorialVenta).order_by(models.HistorialVenta.id.desc()).limit(60).all()
            for v in ultimas_ventas:
                prod = prods_todos_map.get(v.producto_id)
                vendedor = usuarios_map.get(v.vendedor_id)
                dueno = usuarios_map.get(prod.dueno_id) if prod else None
                estado_val = v.estado_venta.value if hasattr(v.estado_venta, "value") else str(v.estado_venta)
                fecha_str = formatear_cancun(v.fecha_venta)

                if estado_val == "Completada" and fecha_str.startswith(hoy_cancun_str):
                    resumen_caja_hoy["total"] += float(v.precio_venta_publico or 0)
                item_venta = {
                    "id": v.id,
                    "producto_id": v.producto_id,
                    "pieza": prod.nombre_refaccion if prod else f"Pieza #{v.producto_id}",
                    "vehiculo": f"{prod.marca} {prod.modelo}" if prod else "",
                    "vendedor": vendedor.nombre if vendedor else "Sistema",
                    "vendedor_id": v.vendedor_id,
                    "dueno": dueno.nombre if dueno else "Bodega",
                    "dueno_id": prod.dueno_id if prod else None,
                    "precio_venta": float(v.precio_venta_publico or 0),
                    "costo_dueno": float(v.precio_costo_dueno or 0),
                    "saldo_por_cobrar": float(v.saldo_por_cobrar or 0),
                    "estado": estado_val,
                    "fecha": fecha_str,
                    "liquidado": bool(v.liquidado_al_dueno)
                }
                ventas_detalle.append(item_venta)
                if usuario and prod and prod.dueno_id == usuario.id:
                    mis_ventas_socio.append(item_venta)

        mi_garaje = db.query(models.GarajeUsuario).filter(models.GarajeUsuario.usuario_id == usuario.id).all() if usuario else []
        mi_taller = db.query(models.PerfilTaller).filter(models.PerfilTaller.usuario_id == usuario.id).first() if usuario else None

        talleres_directorio = []
        for t in db.query(models.PerfilTaller).all():
            u_taller = usuarios_map.get(t.usuario_id)
            if u_taller:
                talleres_directorio.append({
                    "id": t.id, "nombre_taller": t.nombre_taller, "colonia_region": t.colonia_region,
                    "especialidad": t.especialidad, "telefono": u_taller.telefono_celular if usuario else "",
                    "encargado": u_taller.nombre
                })

        solicitudes_raw = db.query(models.SolicitudUrgente).order_by(models.SolicitudUrgente.id.desc()).limit(40).all()
        solicitudes_urgentes = []
        for s in solicitudes_raw:
            u_sol = usuarios_map.get(s.usuario_id)
            resps = [{"id": r.id, "autor": usuarios_map[r.usuario_id].nombre if r.usuario_id in usuarios_map else "Usuario",
                      "telefono": (usuarios_map[r.usuario_id].telefono_celular if (r.usuario_id in usuarios_map and usuario) else ""),
                      "mensaje": r.mensaje, "precio_ofrecido": r.precio_ofrecido} for r in s.respuestas]
            solicitudes_urgentes.append({
                "id": s.id, "usuario_id": s.usuario_id, "autor": u_sol.nombre if u_sol else "Usuario",
                "titulo": s.titulo, "vehiculo": s.vehiculo, "detalles": s.detalles,
                "zona_cancun": s.zona_cancun, "resuelto": bool(s.resuelto), "respuestas": resps
            })

        foros_raw = db.query(models.DiagnosticoForo).order_by(models.DiagnosticoForo.id.desc()).limit(40).all()
        diagnosticos_foro = []
        for f in foros_raw:
            u_foro = usuarios_map.get(f.usuario_id)
            coms = []
            for c in f.comentarios:
                u_com = usuarios_map.get(c.usuario_id)
                rol_com = (u_com.rol.value if hasattr(u_com.rol, "value") else str(u_com.rol)) if u_com else ""
                coms.append({"id": c.id, "autor": u_com.nombre if u_com else "Usuario", "es_mecanico": rol_com in ["Mecanico", "Administrador"], "comentario": c.comentario})
            diagnosticos_foro.append({
                "id": f.id, "usuario_id": f.usuario_id, "autor": u_foro.nombre if u_foro else "Usuario",
                "vehiculo": f.vehiculo, "sintoma": f.sintoma, "descripcion": f.descripcion,
                "solucionado": bool(f.solucionado), "comentarios": coms
            })

        return templates.TemplateResponse("mostrador.html", {
            "request": request, "usuario": usuario, "productos": productos_sanitizados,
            "usuarios": usuarios_admin_lista, "solicitudes_ids": solicitudes_ids,
            "anuncios_mercado": anuncios_mercado, "anuncios_json": json.dumps(anuncios_mercado, ensure_ascii=False),
            "dict_vehiculos": json.dumps(seed.DICCIONARIO_VEHICULOS, ensure_ascii=False),
            "rangos_modelos": json.dumps(seed.RANGOS_MODELOS_MX, ensure_ascii=False),
            "liquidaciones": liquidaciones_pendientes, "ventas_detalle": ventas_detalle,
            "mis_ventas_socio": mis_ventas_socio, "resumen_caja_hoy": resumen_caja_hoy,
            "bitacora": bitacora_lista, "mi_garaje": mi_garaje, "mi_taller": mi_taller,
            "talleres_directorio": talleres_directorio, "solicitudes_urgentes": solicitudes_urgentes,
            "diagnosticos_foro": diagnosticos_foro, "whatsapp_mostrador": WHATSAPP_MOSTRADOR,
            "mis_strikes": strikes_map.get(usuario.id, 0) if usuario else 0
        })
    finally:
        db.close()
            
