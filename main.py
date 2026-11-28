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
        ventas_pendientes = []
        mis_ventas_socio = []
        resumen_caja_hoy = {"efectivo": 0.0, "transferencia": 0.0, "total": 0.0}
        hoy_cancun_str = ahora.astimezone(TZ_CANCUN).strftime("%d/%m/%Y")

        if es_operador:
            prods_todos_map = {p.id: p for p in db.query(models.Producto).all()}

            if es_admin:
                pendientes_raw = db.query(models.HistorialVenta).filter(
                    models.HistorialVenta.liquidado_al_dueno == False,
                    models.HistorialVenta.estado_venta == models.EstadoVentaEnum.Completada
                ).all()
                for v in pendientes_raw:
                    prod = prods_todos_map.get(v.producto_id)
                    dueno = usuarios_map.get(prod.dueno_id) if prod else None
                    if prod and dueno:
                        if dueno.id not in liquidaciones_pendientes:
                            liquidaciones_pendientes[dueno.id] = {"dueno": dueno.nombre, "saldo": 0.0, "items": []}
                        liquidaciones_pendientes[dueno.id]["saldo"] += float(v.saldo_por_cobrar or 0)
                        liquidaciones_pendientes[dueno.id]["items"].append(v.id)

            ultimas_ventas = db.query(models.HistorialVenta).order_by(models.HistorialVenta.id.desc()).limit(80).all()
            for v in ultimas_ventas:
                prod = prods_todos_map.get(v.producto_id)
                vendedor = usuarios_map.get(v.vendedor_id)
                dueno = usuarios_map.get(prod.dueno_id) if prod else None
                estado_val = v.estado_venta.value if hasattr(v.estado_venta, "value") else str(v.estado_venta)
                fecha_str = formatear_cancun(v.fecha_venta)

                if es_admin and estado_val == "Completada" and fecha_str.startswith(hoy_cancun_str):
                    resumen_caja_hoy["total"] += float(v.precio_venta_publico or 0)

                item_venta = {
                    "id": v.id,
                    "producto_id": v.producto_id,
                    "pieza": prod.nombre_refaccion if prod else f"Pieza #{v.producto_id}",
                    "vehiculo": f"{prod.marca} {prod.modelo}" if prod else "",
                    "ubicacion": prod.ubicacion_fisica if prod else "",
                    "vendedor": vendedor.nombre if vendedor else "Sistema",
                    "vendedor_tel": vendedor.telefono_celular if vendedor else "",
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
                if es_admin:
                    ventas_detalle.append(item_venta)
                    if estado_val == "Pendiente":
                        ventas_pendientes.append(item_venta)
                if usuario and ((prod and prod.dueno_id == usuario.id) or v.vendedor_id == usuario.id):
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
            "ventas_pendientes": ventas_pendientes,
            "mis_ventas_socio": mis_ventas_socio, "resumen_caja_hoy": resumen_caja_hoy,
            "bitacora": bitacora_lista, "mi_garaje": mi_garaje, "mi_taller": mi_taller,
            "talleres_directorio": talleres_directorio, "solicitudes_urgentes": solicitudes_urgentes,
            "diagnosticos_foro": diagnosticos_foro, "whatsapp_mostrador": WHATSAPP_MOSTRADOR,
            "mis_strikes": strikes_map.get(usuario.id, 0) if usuario else 0
        })
    finally:
        db.close()
@app.post("/auth/login")
def login(request: Request, usuario: str = Form(...), contrasena: str = Form(...)):
    import database, models, security
    db = next(database.get_db())
    try:
        user = db.query(models.Usuario).filter(models.Usuario.usuario == usuario.strip().lower()).first()
        if not user or not security.verificar_password(contrasena, user.contrasena_hash):
            return RedirectResponse(url="/mostrador?error=Usuario+o+clave+incorrectos", status_code=status.HTTP_303_SEE_OTHER)
        token = security.crear_token_acceso(data={"sub": user.usuario}, usuario=user)
        response = RedirectResponse(url="/mostrador?msg=Bienvenido+de+nuevo", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True, secure=security.es_entorno_seguro(request), samesite="lax", max_age=security.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
        return response
    finally:
        db.close()

@app.post("/auth/registro")
def registrar_usuario_publico(request: Request, nombre: str = Form(...), usuario: str = Form(...), telefono_celular: str = Form(...), contrasena: str = Form(...), solicitar_especial: str = Form(None)):
    import database, models, security
    db = next(database.get_db())
    try:
        user_norm = re.sub(r"[^a-z0-9._-]", "", usuario.strip().lower())
        tel_limpio = re.sub(r"[^\d+]", "", telefono_celular.strip())
        if len(user_norm) < 3:
            return RedirectResponse(url="/mostrador?error=El+usuario+debe+tener+al+menos+3+caracteres", status_code=status.HTTP_303_SEE_OTHER)
        if len(contrasena) < 8:
            return RedirectResponse(url="/mostrador?error=La+contraseña+debe+tener+mínimo+8+caracteres", status_code=status.HTTP_303_SEE_OTHER)
        if len(re.sub(r"\D", "", tel_limpio)) < 10:
            return RedirectResponse(url="/mostrador?error=Ingresa+un+número+celular+válido+a+10+dígitos", status_code=status.HTTP_303_SEE_OTHER)
        if db.query(models.Usuario).filter(models.Usuario.usuario == user_norm).first():
            return RedirectResponse(url="/mostrador?error=Ese+nombre+de+usuario+ya+está+en+uso", status_code=status.HTTP_303_SEE_OTHER)

        nuevo_usuario = models.Usuario(nombre=nombre.strip(), usuario=user_norm, contrasena_hash=security.obtener_password_hash(contrasena), rol=models.RolEnum.Publico_General, telefono_celular=tel_limpio)
        db.add(nuevo_usuario)
        db.commit()
        db.refresh(nuevo_usuario)
        if solicitar_especial == "si":
            db.add(models.BitacoraAuditoria(usuario_id=nuevo_usuario.id, accion_realizada="SOLICITUD_VERIFICACION_ESPECIAL"))
            db.commit()
        token = security.crear_token_acceso(data={"sub": nuevo_usuario.usuario})
        response = RedirectResponse(url="/mostrador?msg=Cuenta+creada+exitosamente", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True, secure=security.es_entorno_seguro(request), samesite="lax", max_age=security.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
        return response
    finally:
        db.close()

@app.get("/auth/logout")
def logout():
    response = RedirectResponse(url="/mostrador", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response

@app.post("/usuarios/aprobar/{user_id}")
def aprobar_usuario(user_id: int, nuevo_rol: str = Form(...), request: Request = None):
    import database, models, security
    db = next(database.get_db())
    try:
        admin = security.PermisoRol(["Administrador"])(security.obtener_usuario_actual(request, db))
        user_target = db.query(models.Usuario).filter(models.Usuario.id == user_id).first()
        if not user_target:
            return RedirectResponse(url="/mostrador?tab=afiliados&error=Usuario+no+encontrado", status_code=status.HTTP_303_SEE_OTHER)
        if nuevo_rol in ["Vendedor", "Mecanico", "Administrador", "Publico_General"]:
            user_target.rol = getattr(models.RolEnum, nuevo_rol)
        db.query(models.BitacoraAuditoria).filter(models.BitacoraAuditoria.usuario_id == user_target.id, models.BitacoraAuditoria.accion_realizada == "SOLICITUD_VERIFICACION_ESPECIAL").delete()
        db.add(models.BitacoraAuditoria(usuario_id=admin.id, accion_realizada=f"[ROL] Asignación de rol {nuevo_rol} a @{user_target.usuario}"))
        db.commit()
        return RedirectResponse(url="/mostrador?tab=afiliados&msg=Rol+actualizado", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/usuarios/reset-password/{user_id}")
def resetear_password_admin(user_id: int, nueva_clave: str = Form(...), request: Request = None):
    import database, models, security
    db = next(database.get_db())
    try:
        admin = security.PermisoRol(["Administrador"])(security.obtener_usuario_actual(request, db))
        if len(nueva_clave.strip()) < 8:
            return RedirectResponse(url="/mostrador?tab=afiliados&error=La+clave+temporal+debe+tener+mínimo+8+caracteres", status_code=status.HTTP_303_SEE_OTHER)
        user_target = db.query(models.Usuario).filter(models.Usuario.id == user_id).first()
        if user_target:
            user_target.contrasena_hash = security.obtener_password_hash(nueva_clave.strip())
            db.add(models.BitacoraAuditoria(usuario_id=admin.id, accion_realizada=f"[SEGURIDAD] Reseteo de contraseña a @{user_target.usuario}"))
            db.commit()
        return RedirectResponse(url="/mostrador?tab=afiliados&msg=Contraseña+temporal+asignada", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/usuarios/quitar-strikes/{user_id}")
def quitar_strikes_admin(user_id: int, request: Request):
    import database, models, security
    db = next(database.get_db())
    try:
        admin = security.PermisoRol(["Administrador"])(security.obtener_usuario_actual(request, db))
        db.query(models.BitacoraAuditoria).filter(models.BitacoraAuditoria.usuario_id == user_id, models.BitacoraAuditoria.accion_realizada == "INCUMPLIMIENTO_SUBASTA").delete()
        db.add(models.BitacoraAuditoria(usuario_id=admin.id, accion_realizada=f"[SUBASTA] Strikes limpiados al usuario #{user_id}"))
        db.commit()
        return RedirectResponse(url="/mostrador?tab=afiliados&msg=Strikes+restablecidos", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()
@app.post("/productos/crear")
def registrar_producto(request: Request, categoria: str = Form(...), nombre_refaccion: str = Form(...), marca: str = Form(...), modelo: str = Form(...), ano_grupo: str = Form(...), compatibilidad: str = Form(None), condicion: str = Form("Original Usada • Pieza Probada"), cantidad_disponible: int = Form(1), ubicacion_fisica: str = Form(...), dueno_id: int = Form(...), precio_real: float = Form(...), precio_sugerido: float = Form(...), url_imagen: str = Form(None), procedencia_nota: str = Form(""), procedencia_archivo: str = Form("")):
    import database, models, security
    db = next(database.get_db())
    try:
        admin = security.PermisoRol(["Administrador"])(security.obtener_usuario_actual(request, db))
        if precio_real < 0 or precio_sugerido <= 0 or cantidad_disponible < 1:
            return RedirectResponse(url="/mostrador?error=Verifica+precios+y+cantidad+válidos", status_code=status.HTTP_303_SEE_OTHER)
        nuevo_prod = models.Producto(categoria=categoria, nombre_refaccion=nombre_refaccion.strip(), marca=marca.strip(), modelo=modelo.strip(), ano_grupo=ano_grupo.strip(), compatibilidad=compatibilidad.strip() if compatibilidad else None, condicion=condicion.strip() or "Original Usada", cantidad_disponible=cantidad_disponible, ubicacion_fisica=ubicacion_fisica.strip(), dueno_id=dueno_id, precio_real=precio_real, precio_sugerido=precio_sugerido)
        db.add(nuevo_prod)
        db.commit()
        db.refresh(nuevo_prod)

        for u_img in subir_fotos_a_storage(url_imagen, "piezas", 6):
            db.add(models.ImagenesPieza(producto_id=nuevo_prod.id, url_imagen=u_img))
        url_doc = subir_archivo_a_storage(procedencia_archivo, "procedencia") if procedencia_archivo else ""
        if procedencia_nota.strip() or url_doc:
            db.add(models.BitacoraAuditoria(usuario_id=admin.id, accion_realizada=f"[PROCEDENCIA #{nuevo_prod.id}] {procedencia_nota.strip()} | URL:{url_doc or ''}"))
        dueno = db.query(models.Usuario).filter(models.Usuario.id == dueno_id).first()
        db.add(models.BitacoraAuditoria(usuario_id=admin.id, accion_realizada=f"[ALTA] Pieza #{nuevo_prod.id} ({nuevo_prod.nombre_refaccion}) | Ubicación: {nuevo_prod.ubicacion_fisica} | Dueño: {dueno.nombre if dueno else dueno_id} | Costo: ${precio_real:,.0f} / Público: ${precio_sugerido:,.0f}"))
        db.commit()
        return RedirectResponse(url="/mostrador?msg=Refacción+registrada+en+bodega", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/productos/editar/{prod_id}")
def editar_producto(prod_id: int, categoria: str = Form(...), nombre_refaccion: str = Form(...), marca: str = Form(...), modelo: str = Form(...), ano_grupo: str = Form(...), compatibilidad: str = Form(""), ubicacion_fisica: str = Form(...), condicion: str = Form("Original Usada"), cantidad_disponible: int = Form(1), dueno_id: int = Form(...), precio_real: float = Form(...), precio_sugerido: float = Form(...), fotos_eliminar: str = Form(""), nuevas_fotos: str = Form(""), procedencia_nota: str = Form(""), procedencia_archivo: str = Form(""), request: Request = None):
    import database, models, security
    db = next(database.get_db())
    try:
        admin = security.PermisoRol(["Administrador"])(security.obtener_usuario_actual(request, db))
        prod = db.query(models.Producto).filter(models.Producto.id == prod_id).first()
        if not prod:
            return RedirectResponse(url="/mostrador?error=Pieza+no+encontrada", status_code=status.HTTP_303_SEE_OTHER)
        cambios = []
        if prod.ubicacion_fisica != ubicacion_fisica.strip():
            cambios.append(f"Ubicación ({prod.ubicacion_fisica} -> {ubicacion_fisica.strip()})")
        if float(prod.precio_sugerido) != float(precio_sugerido):
            cambios.append(f"Precio (${prod.precio_sugerido:,.0f} -> ${precio_sugerido:,.0f})")
        if float(prod.precio_real) != float(precio_real):
            cambios.append(f"Costo (${prod.precio_real:,.0f} -> ${precio_real:,.0f})")

        prod.categoria, prod.nombre_refaccion, prod.marca, prod.modelo, prod.ano_grupo = categoria, nombre_refaccion.strip(), marca.strip(), modelo.strip(), ano_grupo.strip()
        prod.compatibilidad, prod.ubicacion_fisica, prod.condicion = compatibilidad.strip() or None, ubicacion_fisica.strip(), condicion.strip()
        prod.cantidad_disponible, prod.dueno_id, prod.precio_real, prod.precio_sugerido = max(1, cantidad_disponible), dueno_id, max(0.0, precio_real), max(1.0, precio_sugerido)

        if fotos_eliminar:
            ids_borrar = [int(x) for x in fotos_eliminar.split(",") if x.strip().isdigit()]
            if ids_borrar:
                db.query(models.ImagenesPieza).filter(models.ImagenesPieza.producto_id == prod.id, models.ImagenesPieza.id.in_(ids_borrar)).delete(synchronize_session=False)
                cambios.append(f"{len(ids_borrar)} foto(s) eliminada(s)")
        if nuevas_fotos:
            for u_img in subir_fotos_a_storage(nuevas_fotos, "piezas", 6):
                db.add(models.ImagenesPieza(producto_id=prod.id, url_imagen=u_img))
            cambios.append("Fotos nuevas agregadas")
        url_doc = subir_archivo_a_storage(procedencia_archivo, "procedencia") if procedencia_archivo else ""
        if procedencia_nota.strip() or url_doc:
            db.add(models.BitacoraAuditoria(usuario_id=admin.id, accion_realizada=f"[PROCEDENCIA #{prod.id}] {procedencia_nota.strip()} | URL:{url_doc or ''}"))
            cambios.append("Procedencia actualizada")
        db.add(models.BitacoraAuditoria(usuario_id=admin.id, accion_realizada=f"[EDICIÓN] Pieza #{prod.id} ({prod.nombre_refaccion}): {', '.join(cambios) if cambios else 'Actualización general'}"))
        db.commit()
        return RedirectResponse(url="/mostrador?msg=Refacción+actualizada+correctamente", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/productos/eliminar/{prod_id}")
def eliminar_producto_admin(prod_id: int, request: Request):
    import database, models, security
    db = next(database.get_db())
    try:
        admin = security.PermisoRol(["Administrador"])(security.obtener_usuario_actual(request, db))
        prod = db.query(models.Producto).filter(models.Producto.id == prod_id).first()
        if prod:
            nombre_p = prod.nombre_refaccion
            if db.query(models.HistorialVenta).filter(models.HistorialVenta.producto_id == prod.id).first():
                prod.cantidad_disponible = 0
            else:
                db.delete(prod)
            db.add(models.BitacoraAuditoria(usuario_id=admin.id, accion_realizada=f"[BAJA] Pieza #{prod_id} ({nombre_p}) dada de baja"))
            db.commit()
        return RedirectResponse(url="/mostrador?msg=Refacción+dada+de+baja", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/productos/apartar/{prod_id}")
def apartar_producto(prod_id: int, request: Request):
    import database, models, security
    db = next(database.get_db())
    try:
        operador = security.PermisoRol(["Administrador", "Vendedor"])(security.obtener_usuario_actual(request, db))
        prod = db.query(models.Producto).filter(models.Producto.id == prod_id).first()
        if prod:
            ahora = ahora_utc()
            f_ap = a_utc_aware(prod.apartado_hasta)
            if f_ap and f_ap > ahora:
                prod.apartado_hasta = None
                msg, accion_txt = "Apartado+liberado", f"[LIBERADO] Pieza #{prod.id} ({prod.nombre_refaccion}) disponible"
            else:
                prod.apartado_hasta = ahora + timedelta(hours=2)
                msg, accion_txt = "Pieza+apartada+por+2+horas", f"[APARTADO] Pieza #{prod.id} ({prod.nombre_refaccion}) apartada 2h"
            db.add(models.BitacoraAuditoria(usuario_id=operador.id, accion_realizada=accion_txt))
            db.commit()
            return RedirectResponse(url=f"/mostrador?msg={msg}", status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(url="/mostrador", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()
@app.post("/productos/vender/{id}")
def marcar_como_vendido(id: int, request: Request, bg_tasks: BackgroundTasks, metodo_pago: str = Form("Efectivo"), tipo_cliente: str = Form("Publico")):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.PermisoRol(["Administrador", "Vendedor"])(security.obtener_usuario_actual(request, db))
        rol_val = usuario.rol.value if hasattr(usuario.rol, "value") else str(usuario.rol)
        es_admin = (rol_val == "Administrador")

        prod = db.query(models.Producto).filter(models.Producto.id == id).with_for_update().first()
        if not prod or prod.cantidad_disponible <= 0:
            return RedirectResponse(url="/mostrador?error=Stock+no+disponible", status_code=status.HTTP_303_SEE_OTHER)

        precio_cobrado = float(prod.precio_sugerido)
        ganancia_base = precio_cobrado - float(prod.precio_real)
        if tipo_cliente == "Taller" and ganancia_base > 0:
            precio_cobrado = round(precio_cobrado - (ganancia_base * 0.15), 2)

        prod.cantidad_disponible -= 1
        if prod.cantidad_disponible == 0:
            prod.apartado_hasta = None

        estado_inicial = models.EstadoVentaEnum.Completada if es_admin else models.EstadoVentaEnum.Pendiente
        saldo_dueno = float(prod.precio_real) if es_admin else 0.0

        venta = models.HistorialVenta(
            producto_id=prod.id,
            vendedor_id=usuario.id,
            estado_venta=estado_inicial,
            precio_costo_dueno=prod.precio_real,
            precio_venta_publico=precio_cobrado,
            ganancia_comision=round(precio_cobrado - float(prod.precio_real), 2),
            liquidado_al_dueno=False,
            saldo_por_cobrar=saldo_dueno
        )
        db.add(venta)

        if es_admin:
            dueno = db.query(models.Usuario).filter(models.Usuario.id == prod.dueno_id).first()
            if dueno and dueno.telefono_celular:
                bg_tasks.add_task(enviar_alerta_whatsapp_task, dueno.telefono_celular, prod.id, prod.nombre_refaccion)
            db.add(models.BitacoraAuditoria(usuario_id=usuario.id, accion_realizada=f"[VENTA] Pieza #{prod.id} ({prod.nombre_refaccion}) vendida en ${precio_cobrado:,.2f} ({metodo_pago} / {tipo_cliente})"))
            msg_resp = "Venta+registrada+en+caja"
        else:
            db.add(models.BitacoraAuditoria(usuario_id=usuario.id, accion_realizada=f"[SOLICITUD VENTA] @{usuario.usuario} solicitó salida de Pieza #{prod.id} ({prod.nombre_refaccion}) por ${precio_cobrado:,.2f} ({metodo_pago})"))
            msg_resp = "Solicitud+de+venta+enviada+al+Administrador+para+confirmar"

        db.commit()
        return RedirectResponse(url=f"/mostrador?msg={msg_resp}", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/ventas/confirmar/{venta_id}")
def confirmar_venta_admin(venta_id: int, request: Request, bg_tasks: BackgroundTasks):
    import database, models, security
    db = next(database.get_db())
    try:
        admin = security.PermisoRol(["Administrador"])(security.obtener_usuario_actual(request, db))
        venta = db.query(models.HistorialVenta).filter(models.HistorialVenta.id == venta_id).with_for_update().first()
        if venta and venta.estado_venta == models.EstadoVentaEnum.Pendiente:
            venta.estado_venta = models.EstadoVentaEnum.Completada
            venta.saldo_por_cobrar = float(venta.precio_costo_dueno or 0)
            prod = db.query(models.Producto).filter(models.Producto.id == venta.producto_id).first()
            if prod:
                dueno = db.query(models.Usuario).filter(models.Usuario.id == prod.dueno_id).first()
                if dueno and dueno.telefono_celular:
                    bg_tasks.add_task(enviar_alerta_whatsapp_task, dueno.telefono_celular, prod.id, prod.nombre_refaccion)
            db.add(models.BitacoraAuditoria(usuario_id=admin.id, accion_realizada=f"[VENTA CONFIRMADA] Solicitud #{venta.id} aprobada — Pieza #{venta.producto_id} (${venta.precio_venta_publico:,.2f})"))
            db.commit()
        return RedirectResponse(url="/mostrador?msg=Venta+confirmada+y+agregada+a+caja", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/ventas/rechazar/{venta_id}")
def rechazar_venta_admin(venta_id: int, request: Request):
    import database, models, security
    db = next(database.get_db())
    try:
        admin = security.PermisoRol(["Administrador"])(security.obtener_usuario_actual(request, db))
        venta = db.query(models.HistorialVenta).filter(models.HistorialVenta.id == venta_id).with_for_update().first()
        if venta and venta.estado_venta == models.EstadoVentaEnum.Pendiente:
            venta.estado_venta = models.EstadoVentaEnum.Cancelada_Devuelta
            venta.saldo_por_cobrar = 0.0
            prod = db.query(models.Producto).filter(models.Producto.id == venta.producto_id).first()
            if prod:
                prod.cantidad_disponible = (prod.cantidad_disponible or 0) + 1
            db.add(models.BitacoraAuditoria(usuario_id=admin.id, accion_realizada=f"[VENTA RECHAZADA] Solicitud #{venta.id} rechazada — Pieza #{venta.producto_id} reingresada a stock"))
            db.commit()
        return RedirectResponse(url="/mostrador?msg=Solicitud+rechazada+y+pieza+devuelta+al+stock", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/ventas/devolver/{venta_id}")
def devolver_venta(venta_id: int, request: Request):
    import database, models, security
    db = next(database.get_db())
    try:
        admin = security.PermisoRol(["Administrador"])(security.obtener_usuario_actual(request, db))
        venta = db.query(models.HistorialVenta).filter(models.HistorialVenta.id == venta_id).first()
        if venta and venta.estado_venta == models.EstadoVentaEnum.Completada:
            ya_liquidada = bool(venta.liquidado_al_dueno)
            venta.estado_venta = models.EstadoVentaEnum.Cancelada_Devuelta
            if ya_liquidada:
                venta.liquidado_al_dueno = False
                venta.saldo_por_cobrar = -abs(float(venta.precio_costo_dueno or 0))
            else:
                venta.saldo_por_cobrar = 0.0
            prod = db.query(models.Producto).filter(models.Producto.id == venta.producto_id).first()
            if prod:
                prod.cantidad_disponible = (prod.cantidad_disponible or 0) + 1
            db.add(models.BitacoraAuditoria(usuario_id=admin.id, accion_realizada=f"[DEVOLUCIÓN] Venta #{venta.id} cancelada — Pieza #{venta.producto_id} reingresada"))
            db.commit()
        return RedirectResponse(url="/mostrador?tab=ventas&msg=Devolución+procesada", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/liquidaciones/procesar/{dueno_id}")
def procesar_liquidacion(dueno_id: int, ids_ventas: str = Form(""), request: Request = None):
    import database, models, security
    db = next(database.get_db())
    try:
        admin = security.PermisoRol(["Administrador"])(security.obtener_usuario_actual(request, db))
        if ids_ventas:
            lista_ids = [int(x) for x in ids_ventas.split(",") if x.strip().isdigit()]
            ventas = db.query(models.HistorialVenta).filter(models.HistorialVenta.id.in_(lista_ids)).all()
            total_pagado = sum(float(v.saldo_por_cobrar or 0) for v in ventas)
            for v in ventas:
                v.liquidado_al_dueno = True
                v.saldo_por_cobrar = 0.0
            socio = db.query(models.Usuario).filter(models.Usuario.id == dueno_id).first()
            db.add(models.BitacoraAuditoria(usuario_id=admin.id, accion_realizada=f"[LIQUIDACIÓN] Corte liquidado a {socio.nombre if socio else dueno_id} por ${total_pagado:,.2f}"))
            db.commit()
        return RedirectResponse(url="/mostrador?tab=ventas&msg=Liquidación+procesada", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.get("/inventario/exportar/csv")
def exportar_inventario_excel(request: Request, dueno_id: str = "todos"):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.PermisoRol(["Administrador", "Vendedor"])(security.obtener_usuario_actual(request, db))
        rol_val = usuario.rol.value if hasattr(usuario.rol, "value") else str(usuario.rol)
        query = db.query(models.Producto).filter(models.Producto.cantidad_disponible > 0)
        if rol_val != "Administrador" or dueno_id == "mio":
            query = query.filter(models.Producto.dueno_id == usuario.id)
            nombre_archivo, titulo_reporte = f"Inventario_{usuario.usuario}.xlsx", f"INVENTARIO: {usuario.nombre.upper()}"
        elif dueno_id.isdigit():
            socio = db.query(models.Usuario).filter(models.Usuario.id == int(dueno_id)).first()
            query = query.filter(models.Producto.dueno_id == int(dueno_id))
            nombre_archivo, titulo_reporte = f"Inventario_Socio_{dueno_id}.xlsx", f"INVENTARIO AFILIADO: {(socio.nombre if socio else dueno_id).upper()}"
        else:
            nombre_archivo, titulo_reporte = "Inventario_General_AutoStock.xlsx", "INVENTARIO GENERAL DE BODEGA"

        productos = query.order_by(models.Producto.id).all()
        usuarios_map = {u.id: u.nombre for u in db.query(models.Usuario).all()}
        wb = Workbook()
        ws = wb.active
        ws.title = "Inventario"
        ws.append([f"AUTOSTOCK MAYAB — {titulo_reporte} ({formatear_cancun(ahora_utc())})"])
        ws.append(["ID", "Categoría", "Refacción", "Marca", "Modelo", "Años", "Etiquetas", "Ubicación", "Dueño", "Cant.", "Costo Unit.", "Público Unit."])
        for cell in ws:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
        for p in productos:
            cat = p.categoria.value if hasattr(p.categoria, "value") else str(p.categoria)
            ws.append([p.id, cat, p.nombre_refaccion, p.marca, p.modelo, p.ano_grupo, p.condicion, p.ubicacion_fisica, usuarios_map.get(p.dueno_id, "Bodega"), int(p.cantidad_disponible or 1), float(p.precio_real or 0), float(p.precio_sugerido or 0)])
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'})
    finally:
        db.close()

@app.get("/inventario/reporte/pdf", response_class=HTMLResponse)
def reporte_imprimible_pdf(request: Request, dueno_id: str = "todos"):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.PermisoRol(["Administrador", "Vendedor"])(security.obtener_usuario_actual(request, db))
        rol_val = usuario.rol.value if hasattr(usuario.rol, "value") else str(usuario.rol)
        query = db.query(models.Producto).filter(models.Producto.cantidad_disponible > 0)
        if rol_val != "Administrador" or dueno_id == "mio":
            query = query.filter(models.Producto.dueno_id == usuario.id)
            titulo = f"Inventario: {usuario.nombre}"
        elif dueno_id.isdigit():
            socio = db.query(models.Usuario).filter(models.Usuario.id == int(dueno_id)).first()
            query = query.filter(models.Producto.dueno_id == int(dueno_id))
            titulo = f"Inventario Afiliado: {socio.nombre if socio else dueno_id}"
        else:
            titulo = "Inventario General de Bodega"
        productos = query.order_by(models.Producto.id).all()
        usuarios_map = {u.id: u.nombre for u in db.query(models.Usuario).all()}
        filas = "".join(f"<tr><td>#{p.id}</td><td><b>{p.nombre_refaccion}</b><br><small>{p.marca} {p.modelo} ({p.ano_grupo})</small></td><td>{p.ubicacion_fisica}</td><td>{usuarios_map.get(p.dueno_id, 'Bodega')}</td><td>{p.cantidad_disponible}</td><td>${p.precio_real:,.2f}</td><td>${p.precio_sugerido:,.2f}</td></tr>" for p in productos)
        t_costo = sum(float(p.precio_real or 0) * int(p.cantidad_disponible or 1) for p in productos)
        t_pub = sum(float(p.precio_sugerido or 0) * int(p.cantidad_disponible or 1) for p in productos)
        return HTMLResponse(f'<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><title>{titulo}</title><style>body{{font-family:sans-serif;padding:15px}}table{{width:100%;border-collapse:collapse;font-size:11px}}th,td{{border-bottom:1px solid #ddd;padding:7px;text-align:left}}th{{background:#0f172a;color:#fff}}.btn{{background:#ea580c;color:#fff;border:none;padding:12px;width:100%;font-weight:bold;border-radius:8px;margin-bottom:15px;cursor:pointer}}@media print{{.btn{{display:none}}}}</style></head><body><button class="btn" onclick="window.print()">🖨️ Guardar PDF / Imprimir</button><h2>⚙️ AutoStock Mayab - {titulo}</h2><p>Fecha Cancún: {formatear_cancun(ahora_utc())} | Registros: {len(productos)}</p><table><thead><tr><th>ID</th><th>Refacción</th><th>Ubicación</th><th>Dueño</th><th>Cant.</th><th>Costo</th><th>Público</th></tr></thead><tbody>{filas}</tbody></table><h3 style="text-align:right">Total Costo: ${t_costo:,.2f} | Total Público: ${t_pub:,.2f}</h3></body></html>')
    finally:
        db.close()
@app.post("/garaje/agregar")
def agregar_garaje(request: Request, marca: str = Form(...), modelo: str = Form(...), ano: str = Form(...), apodo: str = Form("")):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        if not usuario:
            return RedirectResponse(url="/mostrador?tab=garaje&error=Inicia+sesión+para+guardar+en+tu+cuenta", status_code=status.HTTP_303_SEE_OTHER)
        db.add(models.GarajeUsuario(usuario_id=usuario.id, marca=marca.strip(), modelo=modelo.strip(), ano=ano.strip(), apodo=apodo.strip()))
        db.commit()
        return RedirectResponse(url="/mostrador?tab=garaje&msg=Vehículo+guardado+en+Mi+Garaje", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/garaje/eliminar/{auto_id}")
def eliminar_garaje(auto_id: int, request: Request):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        auto = db.query(models.GarajeUsuario).filter(models.GarajeUsuario.id == auto_id).first()
        if usuario and auto and auto.usuario_id == usuario.id:
            db.delete(auto)
            db.commit()
        return RedirectResponse(url="/mostrador?tab=garaje&msg=Vehículo+eliminado", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/taller/guardar-perfil")
def guardar_perfil_taller(request: Request, nombre_taller: str = Form(...), colonia_region: str = Form(...), especialidad: str = Form("Mecánica General"), margen_porcentaje: float = Form(15.0), pin_seguridad: str = Form("1234")):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        if not usuario:
            return RedirectResponse(url="/mostrador?error=Inicia+sesión+primero", status_code=status.HTTP_303_SEE_OTHER)
        pin_limpio = re.sub(r"\D", "", pin_seguridad)[:4] or "1234"
        margen_seguro = max(0.0, min(200.0, margen_porcentaje))
        perfil = db.query(models.PerfilTaller).filter(models.PerfilTaller.usuario_id == usuario.id).first()
        if perfil:
            perfil.nombre_taller, perfil.colonia_region, perfil.especialidad, perfil.margen_porcentaje, perfil.pin_seguridad = nombre_taller.strip(), colonia_region.strip(), especialidad.strip(), margen_seguro, pin_limpio
        else:
            db.add(models.PerfilTaller(usuario_id=usuario.id, nombre_taller=nombre_taller.strip(), colonia_region=colonia_region.strip(), especialidad=especialidad.strip(), margen_porcentaje=margen_seguro, pin_seguridad=pin_limpio))
        db.commit()
        return RedirectResponse(url="/mostrador?tab=comunidad&msg=Perfil+de+Taller+actualizado", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/taller/verificar-pin")
async def verificar_pin_taller(request: Request):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        if not usuario:
            return JSONResponse({"ok": False}, status_code=401)
        data = await request.json()
        perfil = db.query(models.PerfilTaller).filter(models.PerfilTaller.usuario_id == usuario.id).first()
        return JSONResponse({"ok": str(data.get("pin", "")).strip() == (perfil.pin_seguridad if perfil else "1234")})
    finally:
        db.close()
@app.post("/mercado/publicar")
def publicar_anuncio_mercado(request: Request, titulo: str = Form(...), categoria: str = Form(...), precio: float = Form(0.0), descripcion: str = Form(...), zona_cancun: str = Form("Cancún Centro"), es_subasta: str = Form("no"), url_imagen: str = Form(None)):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        if not usuario or precio < 0:
            return RedirectResponse(url="/mostrador?tab=mercado&error=Verifica+tu+sesión+y+precio", status_code=status.HTTP_303_SEE_OTHER)
        urls_mercado = subir_fotos_a_storage(url_imagen, "mercado", 10)
        es_sub = (es_subasta == "si")
        db.add(models.AnuncioMercado(titulo=titulo.strip(), categoria=categoria, precio=precio, descripcion=descripcion.strip(), zona_cancun=zona_cancun.strip(), url_imagen=json.dumps(urls_mercado) if urls_mercado else None, usuario_id=usuario.id, es_subasta=es_sub, subasta_fin=(ahora_utc() + timedelta(hours=24)) if es_sub else None, puja_actual=precio if es_sub else 0.0))
        db.commit()
        return RedirectResponse(url="/mostrador?tab=mercado&msg=Publicado+en+Mercado+Local", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/mercado/pujar/{anuncio_id}")
def pujar_subasta(anuncio_id: int, monto: float = Form(...), request: Request = None):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        if not usuario:
            return RedirectResponse(url="/mostrador?tab=mercado&error=Inicia+sesión+para+pujar", status_code=status.HTTP_303_SEE_OTHER)
        if db.query(models.BitacoraAuditoria).filter(models.BitacoraAuditoria.usuario_id == usuario.id, models.BitacoraAuditoria.accion_realizada == "INCUMPLIMIENTO_SUBASTA").count() >= 2:
            return RedirectResponse(url="/mostrador?tab=mercado&error=Cuenta+bloqueada+en+subastas+por+incumplimientos", status_code=status.HTTP_303_SEE_OTHER)
        anuncio = db.query(models.AnuncioMercado).filter(models.AnuncioMercado.id == anuncio_id).first()
        ahora = ahora_utc()
        fin_sub = a_utc_aware(anuncio.subasta_fin) if anuncio else None
        if not anuncio or not anuncio.es_subasta or anuncio.vendido or (fin_sub and fin_sub <= ahora) or anuncio.usuario_id == usuario.id:
            return RedirectResponse(url="/mostrador?tab=mercado&error=Subasta+no+disponible", status_code=status.HTTP_303_SEE_OTHER)
        minimo = float(anuncio.puja_actual or anuncio.precio or 0) + 50.0
        if monto < minimo:
            return RedirectResponse(url=f"/mostrador?tab=mercado&error=Puja+mínima+\${int(minimo)}", status_code=status.HTTP_303_SEE_OTHER)
        anuncio.puja_actual, anuncio.ganador_id = monto, usuario.id
        if fin_sub and (fin_sub - ahora).total_seconds() <= 30:
            anuncio.subasta_fin = fin_sub + timedelta(minutes=2)
        db.add(models.PujaSubasta(anuncio_id=anuncio.id, usuario_id=usuario.id, monto=monto))
        db.commit()
        return RedirectResponse(url="/mostrador?tab=mercado&msg=Puja+registrada", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/mercado/subasta-incumplida/{anuncio_id}")
def reportar_ganador_incumplido(anuncio_id: int, request: Request):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        anuncio = db.query(models.AnuncioMercado).filter(models.AnuncioMercado.id == anuncio_id).first()
        rol_val = (usuario.rol.value if hasattr(usuario.rol, "value") else str(usuario.rol)) if usuario else ""
        if usuario and anuncio and (anuncio.usuario_id == usuario.id or rol_val == "Administrador") and anuncio.ganador_id:
            ganador_fallido = anuncio.ganador_id
            db.add(models.BitacoraAuditoria(usuario_id=ganador_fallido, accion_realizada="INCUMPLIMIENTO_SUBASTA"))
            db.query(models.PujaSubasta).filter(models.PujaSubasta.anuncio_id == anuncio.id, models.PujaSubasta.usuario_id == ganador_fallido).delete()
            db.flush()
            sig = db.query(models.PujaSubasta).filter(models.PujaSubasta.anuncio_id == anuncio.id).order_by(models.PujaSubasta.monto.desc()).first()
            if sig:
                anuncio.ganador_id, anuncio.puja_actual = sig.usuario_id, sig.monto
            else:
                anuncio.ganador_id, anuncio.puja_actual, anuncio.subasta_fin = None, anuncio.precio, ahora_utc() + timedelta(hours=24)
            db.commit()
        return RedirectResponse(url="/mostrador?tab=mercado&msg=Strike+aplicado+y+subasta+actualizada", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/mercado/vendido/{anuncio_id}")
def marcar_anuncio_vendido(anuncio_id: int, request: Request):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        anuncio = db.query(models.AnuncioMercado).filter(models.AnuncioMercado.id == anuncio_id).first()
        rol_val = (usuario.rol.value if hasattr(usuario.rol, "value") else str(usuario.rol)) if usuario else ""
        if usuario and anuncio and (anuncio.usuario_id == usuario.id or rol_val == "Administrador"):
            anuncio.vendido = True
            db.commit()
        return RedirectResponse(url="/mostrador?tab=mercado&msg=Marcado+como+vendido", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/mercado/eliminar/{anuncio_id}")
def eliminar_anuncio_mercado(anuncio_id: int, request: Request):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        anuncio = db.query(models.AnuncioMercado).filter(models.AnuncioMercado.id == anuncio_id).first()
        rol_val = (usuario.rol.value if hasattr(usuario.rol, "value") else str(usuario.rol)) if usuario else ""
        if usuario and anuncio and (anuncio.usuario_id == usuario.id or rol_val == "Administrador"):
            db.delete(anuncio)
            db.commit()
        return RedirectResponse(url="/mostrador?tab=mercado&msg=Publicación+eliminada", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()
@app.post("/urgente/crear")
def crear_solicitud_urgente(request: Request, titulo: str = Form(...), vehiculo: str = Form(...), detalles: str = Form(...), zona_cancun: str = Form("Cancún")):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        if usuario:
            db.add(models.SolicitudUrgente(usuario_id=usuario.id, titulo=titulo.strip(), vehiculo=vehiculo.strip(), detalles=detalles.strip(), zona_cancun=zona_cancun.strip()))
            db.commit()
        return RedirectResponse(url="/mostrador?tab=mercado&sub=busco&msg=Solicitud+publicada", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/urgente/responder/{sol_id}")
def responder_solicitud_urgente(sol_id: int, mensaje: str = Form(...), precio_ofrecido: float = Form(None), request: Request = None):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        if usuario:
            db.add(models.RespuestaUrgente(solicitud_id=sol_id, usuario_id=usuario.id, mensaje=mensaje.strip(), precio_ofrecido=precio_ofrecido))
            db.commit()
        return RedirectResponse(url="/mostrador?tab=mercado&sub=busco&msg=Respuesta+enviada", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/urgente/cerrar/{sol_id}")
def cerrar_solicitud_urgente(sol_id: int, request: Request):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        sol = db.query(models.SolicitudUrgente).filter(models.SolicitudUrgente.id == sol_id).first()
        rol_val = (usuario.rol.value if hasattr(usuario.rol, "value") else str(usuario.rol)) if usuario else ""
        if usuario and sol and (sol.usuario_id == usuario.id or rol_val == "Administrador"):
            sol.resuelto = True
            db.commit()
        return RedirectResponse(url="/mostrador?tab=mercado&sub=busco&msg=Solicitud+cerrada", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/diagnostico/crear")
def crear_diagnostico(request: Request, vehiculo: str = Form(...), sintoma: str = Form(...), descripcion: str = Form(...)):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        if usuario:
            db.add(models.DiagnosticoForo(usuario_id=usuario.id, vehiculo=vehiculo.strip(), sintoma=sintoma.strip(), descripcion=descripcion.strip()))
            db.commit()
        return RedirectResponse(url="/mostrador?tab=comunidad&msg=Consulta+publicada", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/diagnostico/comentar/{foro_id}")
def comentar_diagnostico(foro_id: int, comentario: str = Form(...), request: Request = None):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        if usuario:
            db.add(models.ComentarioDiagnostico(diagnostico_id=foro_id, usuario_id=usuario.id, comentario=comentario.strip()))
            db.commit()
        return RedirectResponse(url="/mostrador?tab=comunidad&msg=Aporte+publicado", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/diagnostico/solucionado/{foro_id}")
def solucionar_diagnostico(foro_id: int, request: Request):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        foro = db.query(models.DiagnosticoForo).filter(models.DiagnosticoForo.id == foro_id).first()
        rol_val = (usuario.rol.value if hasattr(usuario.rol, "value") else str(usuario.rol)) if usuario else ""
        if usuario and foro and (foro.usuario_id == usuario.id or rol_val == "Administrador"):
            foro.solucionado = True
            db.commit()
        return RedirectResponse(url="/mostrador?tab=comunidad&msg=Marcado+como+solucionado", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/diagnostico/eliminar/{foro_id}")
def eliminar_diagnostico_admin(foro_id: int, request: Request):
    import database, models, security
    db = next(database.get_db())
    try:
        admin = security.PermisoRol(["Administrador"])(security.obtener_usuario_actual(request, db))
        foro = db.query(models.DiagnosticoForo).filter(models.DiagnosticoForo.id == foro_id).first()
        if foro:
            db.delete(foro)
            db.add(models.BitacoraAuditoria(usuario_id=admin.id, accion_realizada=f"[MODERACIÓN] Consulta #{foro_id} eliminada"))
            db.commit()
        return RedirectResponse(url="/mostrador?tab=comunidad&msg=Consulta+eliminada", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.get("/ping")
def mantener_despierto():
    return {"estado": "activo", "hora_cancun": formatear_cancun(ahora_utc())}
        
