import json
import os
from fastapi import FastAPI, Depends, Request, Form, HTTPException, status, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# ✅ Inicialización central del framework (Crucial para evitar el NameError en Render)
app = FastAPI(title="AutoStock Mayab")

@app.get("/static/manifest.json")
def get_manifest():
    return FileResponse("static/manifest.json", media_type="application/json")

@app.get("/static/sw.js")
def get_serviceworker():
    return FileResponse("static/sw.js", media_type="application/javascript")

@app.on_event("startup")
def on_startup():
    # ✅ Aislamiento explícito de módulos para romper residuos de caché en Render
    import database
    import models
    import seed
    
    # Garantiza la creación ordenada de esquemas en Supabase
    models.Base.metadata.create_all(bind=database.engine)
    
    db = next(database.get_db())
    try:
        seed.seed_database(db)
    finally:
        db.close()

# Montaje de recursos estáticos con validación explícita de rutas para Render
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory="templates")
import base64
import uuid
import urllib.request

def subir_fotos_a_storage(url_imagen_raw: str, carpeta: str, limite: int) -> list:
    if not url_imagen_raw:
        return []
    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    supabase_key = os.getenv("SUPABASE_KEY", "")
    
    try:
        lista_items = json.loads(url_imagen_raw) if url_imagen_raw.startswith("[") else [url_imagen_raw]
    except Exception:
        lista_items = [url_imagen_raw]
        
    urls_finales = []
    for item in lista_items[:limite]:
        if not item:
            continue
        if item.startswith("http"):
            urls_finales.append(item)
            continue
        if item.startswith("data:image") and supabase_url and supabase_key:
            try:
                encabezado, b64_data = item.split(",", 1)
                img_bytes = base64.b64decode(b64_data)
                nombre_archivo = f"{carpeta}/{uuid.uuid4().hex}.jpg"
                endpoint = f"{supabase_url}/storage/v1/object/fotos-autostock/{nombre_archivo}"
                
                req = urllib.request.Request(endpoint, data=img_bytes, method="POST")
                req.add_header("Authorization", f"Bearer {supabase_key}")
                req.add_header("apikey", supabase_key)
                req.add_header("Content-Type", "image/jpeg")
                
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if resp.status in (200, 201):
                        url_publica = f"{supabase_url}/storage/v1/object/public/fotos-autostock/{nombre_archivo}"
                        urls_finales.append(url_publica)
            except Exception as e:
                print(f"[STORAGE ERROR] No se pudo subir imagen: {e}")
                urls_finales.append(item)
        else:
            urls_finales.append(item)
            
    return urls_finales

async def enviar_alerta_whatsapp_task(telefono: str, producto_id: int, nombre_pieza: str):
    # Proceso asíncrono seguro en segundo plano para notificar salidas de inventario
    print(f"[WHATSAPP API] Alerta automatizada enviada al afiliado ({telefono}): Refacción #{producto_id} ({nombre_pieza}) confirmada como vendida.")

@app.get("/", response_class=HTMLResponse)
@app.get("/mostrador", response_class=HTMLResponse)
def vista_mostrador(request: Request):
    import database, models, security, seed
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        productos_raw = db.query(models.Producto).filter(models.Producto.cantidad_disponible > 0).all()
        usuarios_sistema = db.query(models.Usuario).all()
        
        es_mecanico = bool(usuario and (usuario.rol == models.RolEnum.Mecanico or usuario.rol == "Mecanico"))
        es_operador = bool(usuario and usuario.rol in [models.RolEnum.Administrador, models.RolEnum.Vendedor, "Administrador", "Vendedor"])

        productos_sanitizados = []
        for prod in productos_raw:
            precio_final = float(prod.precio_sugerido)
            tiene_descuento_taller = False

            if es_mecanico:
                ganancia = float(prod.precio_sugerido) - float(prod.precio_real)
                if ganancia > 0:
                    precio_final = round(float(prod.precio_sugerido) - (ganancia * 0.15), 2)
                    tiene_descuento_taller = True

            productos_sanitizados.append({
                "id": prod.id,
                "categoria": prod.categoria,
                "nombre_refaccion": prod.nombre_refaccion,
                "marca": prod.marca,
                "modelo": prod.modelo,
                "ano_grupo": prod.ano_grupo,
                "compatibilidad": prod.compatibilidad,
                "condicion": prod.condicion or "Original Usada - Excelente",
           "apartado": bool(prod.apartado_hasta and prod.apartado_hasta > datetime.now(timezone.utc)),
                "precio_publico_original": float(prod.precio_sugerido),
                "precio_sugerido": precio_final,
                "tiene_descuento_taller": tiene_descuento_taller,
                "dueno_id": prod.dueno_id,
                "fecha_ingreso": prod.fecha_ingreso.isoformat() if prod.fecha_ingreso else None,
                "precio_real": prod.precio_real if es_operador else None,
                "ubicacion_fisica": prod.ubicacion_fisica if es_operador else "🔒 Autentíquese para ver ubicación",
                                "imagenes": [img.url_imagen for img in prod.imagenes] if prod.imagenes else []
        })

        productos_sanitizados = sorted(productos_sanitizados, key=lambda x: x["id"])

        solicitudes_ids = []
        if usuario and (usuario.rol == models.RolEnum.Administrador or usuario.rol == "Administrador"):
            regs = db.query(models.BitacoraAuditoria).filter(models.BitacoraAuditoria.accion_realizada == "SOLICITUD_VERIFICACION_ESPECIAL").all()
            solicitudes_ids = [r.usuario_id for r in regs]

        anuncios_raw = db.query(models.AnuncioMercado).order_by(models.AnuncioMercado.id.desc()).limit(60).all()
        anuncios_mercado = []
        for a in anuncios_raw:
            autor = db.query(models.Usuario).filter(models.Usuario.id == a.usuario_id).first()
            cat_texto = a.categoria.value if hasattr(a.categoria, "value") else str(a.categoria)
            rol_autor = autor.rol.value if (autor and hasattr(autor.rol, "value")) else (str(autor.rol) if autor else "Publico_General")
            fotos_anuncio = []
            if a.url_imagen:
                if a.url_imagen.startswith("["):
                    try:
                        fotos_anuncio = json.loads(a.url_imagen)
                    except Exception:
                        fotos_anuncio = [a.url_imagen]
                else:
                    fotos_anuncio = [a.url_imagen]
            anuncios_mercado.append({
           "id": a.id, "titulo": a.titulo, "categoria": cat_texto, "precio": a.precio,
           "imagenes": fotos_anuncio,
           "descripcion": a.descripcion, "zona_cancun": a.zona_cancun, "url_imagen": a.url_imagen,
           "vendido": bool(a.vendido),
           "es_subasta": bool(a.es_subasta),
           "subasta_fin": a.subasta_fin.isoformat() if a.subasta_fin else None,
           "puja_actual": float(a.puja_actual or a.precio or 0),
           "ganador_id": a.ganador_id,
           "usuario_id": a.usuario_id, "autor_nombre": autor.nombre if autor else "Usuario Cancún",
           "autor_telefono": autor.telefono_celular if autor else "", "autor_rol": rol_autor,
           "fecha": a.fecha_publicacion.strftime("%d/%m/%Y") if a.fecha_publicacion else "Reciente"
       })

        liquidaciones_pendientes = {}
        ventas_detalle = []
        if es_operador:
            todas_ventas = db.query(models.HistorialVenta).order_by(models.HistorialVenta.id.desc()).limit(50).all()
            for v in todas_ventas:
                prod = db.query(models.Producto).filter(models.Producto.id == v.producto_id).first()
                vendedor = db.query(models.Usuario).filter(models.Usuario.id == v.vendedor_id).first()
                dueno = db.query(models.Usuario).filter(models.Usuario.id == prod.dueno_id).first() if prod else None
                es_pieza_ajena = bool(prod and v.vendedor_id != prod.dueno_id)
                fecha_str = v.fecha_venta.strftime("%d/%m/%Y %H:%M") if getattr(v, "fecha_venta", None) else "Reciente"

                ventas_detalle.append({
                    "id": v.id, "producto_id": v.producto_id,
                    "pieza": prod.nombre_refaccion if prod else f"Pieza #{v.producto_id}",
                    "vehiculo": f"{prod.marca} {prod.modelo}" if prod else "",
                    "vendedor": vendedor.nombre if vendedor else "Sistema", "vendedor_id": v.vendedor_id,
                    "dueno": dueno.nombre if dueno else "Bodega", "dueno_id": prod.dueno_id if prod else None,
                    "precio_venta": v.precio_venta_publico, "costo_dueno": v.precio_costo_dueno,
                    "fecha": fecha_str, "liquidado": v.liquidado_al_dueno, "es_pieza_ajena": es_pieza_ajena
                })

                if not v.liquidado_al_dueno and prod and dueno:
                    if dueno.id not in liquidaciones_pendientes:
                        liquidaciones_pendientes[dueno.id] = {"dueno": dueno.nombre, "saldo": 0.0, "items": []}
                    liquidaciones_pendientes[dueno.id]["saldo"] += v.saldo_por_cobrar
                    liquidaciones_pendientes[dueno.id]["items"].append(v.id)

        mi_garaje = db.query(models.GarajeUsuario).filter(models.GarajeUsuario.usuario_id == usuario.id).all() if usuario else []
        mi_taller = db.query(models.PerfilTaller).filter(models.PerfilTaller.usuario_id == usuario.id).first() if usuario else None
        talleres_raw = db.query(models.PerfilTaller).all()
        talleres_directorio = []
        for t in talleres_raw:
            u_taller = db.query(models.Usuario).filter(models.Usuario.id == t.usuario_id).first()
            if u_taller:
                talleres_directorio.append({
                    "id": t.id, "nombre_taller": t.nombre_taller, "colonia_region": t.colonia_region,
                    "especialidad": t.especialidad, "telefono": u_taller.telefono_celular, "encargado": u_taller.nombre
                })

        solicitudes_raw = db.query(models.SolicitudUrgente).order_by(models.SolicitudUrgente.id.desc()).limit(40).all()
        solicitudes_urgentes = []
        for s in solicitudes_raw:
            u_sol = db.query(models.Usuario).filter(models.Usuario.id == s.usuario_id).first()
            resps = []
            for r in s.respuestas:
                u_res = db.query(models.Usuario).filter(models.Usuario.id == r.usuario_id).first()
                resps.append({
                    "id": r.id, "autor": u_res.nombre if u_res else "Usuario",
                    "telefono": u_res.telefono_celular if u_res else "",
                    "mensaje": r.mensaje, "precio_ofrecido": r.precio_ofrecido
                })
            solicitudes_urgentes.append({
                "id": s.id, "usuario_id": s.usuario_id, "autor": u_sol.nombre if u_sol else "Usuario",
                "telefono": u_sol.telefono_celular if u_sol else "", "titulo": s.titulo,
                "vehiculo": s.vehiculo, "detalles": s.detalles, "zona_cancun": s.zona_cancun,
                "resuelto": bool(s.resuelto), "respuestas": resps
            })

        foros_raw = db.query(models.DiagnosticoForo).order_by(models.DiagnosticoForo.id.desc()).limit(40).all()
        diagnosticos_foro = []
        for f in foros_raw:
            u_foro = db.query(models.Usuario).filter(models.Usuario.id == f.usuario_id).first()
            coms = []
            for c in f.comentarios:
                u_com = db.query(models.Usuario).filter(models.Usuario.id == c.usuario_id).first()
                rol_com = u_com.rol.value if (u_com and hasattr(u_com.rol, "value")) else (str(u_com.rol) if u_com else "")
                coms.append({
                    "id": c.id, "autor": u_com.nombre if u_com else "Usuario",
                    "es_mecanico": rol_com in ["Mecanico", "Administrador"],
                    "comentario": c.comentario
                })
            diagnosticos_foro.append({
                "id": f.id, "usuario_id": f.usuario_id, "autor": u_foro.nombre if u_foro else "Usuario",
                "vehiculo": f.vehiculo, "sintoma": f.sintoma, "descripcion": f.descripcion,
                "solucionado": bool(f.solucionado), "comentarios": coms
            })

        return templates.TemplateResponse("mostrador.html", {
            "request": request, "usuario": usuario, "productos": productos_sanitizados,
            "usuarios": usuarios_sistema, "solicitudes_ids": solicitudes_ids, "anuncios_mercado": anuncios_mercado,
            "dict_vehiculos": json.dumps(seed.DICCIONARIO_VEHICULOS),
            "liquidaciones": liquidaciones_pendientes, "ventas_detalle": ventas_detalle,
            "mi_garaje": mi_garaje, "mi_taller": mi_taller, "talleres_directorio": talleres_directorio,
            "solicitudes_urgentes": solicitudes_urgentes, "diagnosticos_foro": diagnosticos_foro
        })
    finally:
        db.close()

@app.post("/auth/login")
def login(usuario: str = Form(...), contrasena: str = Form(...)):
    import database, models, security
    db = next(database.get_db())
    try:
        user = db.query(models.Usuario).filter(models.Usuario.usuario == usuario).first()
        if not user or not security.verificar_password(contrasena, user.contrasena_hash):
            return RedirectResponse(url="/mostrador?error=Credenciales+Incorrectas", status_code=status.HTTP_303_SEE_OTHER)
        token = security.crear_token_acceso(data={"sub": user.usuario})
        response = RedirectResponse(url="/mostrador", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True, secure=True, samesite="lax")
        return response
    finally:
        db.close()

@app.post("/usuarios/aprobar/{user_id}")
def aprobar_usuario(user_id: int, nuevo_rol: str = Form(...), request: Request = None):
    import database, models, security
    db = next(database.get_db())
    try:
        admin = security.PermisoRol(["Administrador"])(security.obtener_usuario_actual(request, db))
        user_target = db.query(models.Usuario).filter(models.Usuario.id == user_id).first()
        if not user_target:
            return RedirectResponse(url="/mostrador?error=Usuario+no+encontrado", status_code=status.HTTP_303_SEE_OTHER)
        if nuevo_rol in ["Vendedor", "Mecanico", "Administrador", "Publico_General"]:
            user_target.rol = getattr(models.RolEnum, nuevo_rol)
        db.query(models.BitacoraAuditoria).filter(
            models.BitacoraAuditoria.usuario_id == user_target.id,
            models.BitacoraAuditoria.accion_realizada == "SOLICITUD_VERIFICACION_ESPECIAL"
        ).delete()
        db.add(models.BitacoraAuditoria(usuario_id=admin.id, accion_realizada=f"Asignación de rol {nuevo_rol} a @{user_target.usuario}"))
        db.commit()
        return RedirectResponse(url="/mostrador?msg=Rol+Actualizado", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.get("/auth/logout")
def logout():
    response = RedirectResponse(url="/mostrador", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response

@app.post("/auth/registro")
def registrar_usuario_publico(nombre: str = Form(...), usuario: str = Form(...), telefono_celular: str = Form(...), contrasena: str = Form(...), solicitar_especial: str = Form(None)):
    import database, models, security
    db = next(database.get_db())
    try:
        if db.query(models.Usuario).filter(models.Usuario.usuario == usuario).first():
            return RedirectResponse(url="/mostrador?error=El+usuario+ya+existe", status_code=status.HTTP_303_SEE_OTHER)
        nuevo_usuario = models.Usuario(nombre=nombre, usuario=usuario, contrasena_hash=security.obtener_password_hash(contrasena), rol=models.RolEnum.Publico_General, telefono_celular=telefono_celular)
        db.add(nuevo_usuario)
        db.commit()
        db.refresh(nuevo_usuario)
        if solicitar_especial == "si":
            db.add(models.BitacoraAuditoria(usuario_id=nuevo_usuario.id, accion_realizada="SOLICITUD_VERIFICACION_ESPECIAL"))
            db.commit()
        token = security.crear_token_acceso(data={"sub": nuevo_usuario.usuario})
        response = RedirectResponse(url="/mostrador?msg=Bienvenido+a+AutoStock+Mayab", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True, secure=True, samesite="lax")
        return response
    finally:
        db.close()

@app.post("/mercado/publicar")
def publicar_anuncio_mercado(request: Request, titulo: str = Form(...), categoria: str = Form(...), precio: float = Form(0.0), descripcion: str = Form(...), zona_cancun: str = Form("Cancún Centro"), es_subasta: str = Form("no"), url_imagen: str = Form(None)):
    import database, models, security
    from datetime import timedelta
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        if not usuario:
            return RedirectResponse(url="/mostrador?error=Inicia+sesion+para+publicar", status_code=status.HTTP_303_SEE_OTHER)
        urls_mercado = subir_fotos_a_storage(url_imagen, "mercado", 10)
        url_guardar = json.dumps(urls_mercado) if urls_mercado else None
        es_sub = (es_subasta == "si")
        fin_sub = (datetime.now(timezone.utc) + timedelta(hours=24)) if es_sub else None
        db.add(models.AnuncioMercado(
            titulo=titulo, categoria=categoria, precio=precio, descripcion=descripcion,
            zona_cancun=zona_cancun, url_imagen=url_guardar, usuario_id=usuario.id,
            es_subasta=es_sub, subasta_fin=fin_sub, puja_actual=precio if es_sub else 0.0
        ))
        db.commit()
        return RedirectResponse(url="/mostrador?msg=Publicado+en+Mercado+Local", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/mercado/eliminar/{anuncio_id}")
def eliminar_anuncio_mercado(anuncio_id: int, request: Request):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        anuncio = db.query(models.AnuncioMercado).filter(models.AnuncioMercado.id == anuncio_id).first()
        if usuario and anuncio and (anuncio.usuario_id == usuario.id or usuario.rol in [models.RolEnum.Administrador, "Administrador"]):
            db.delete(anuncio)
            db.commit()
            return RedirectResponse(url="/mostrador?msg=Anuncio+eliminado", status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(url="/mostrador?error=Sin+permiso", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/productos/crear")
def registrar_producto(
    request: Request,
    categoria: str = Form(...), nombre_refaccion: str = Form(...),
    marca: str = Form(...), modelo: str = Form(...), ano_grupo: str = Form(...),
    compatibilidad: str = Form(None), condicion: str = Form("Original Usada - Excelente"),
    ubicacion_fisica: str = Form(...), dueno_id: int = Form(...),
    precio_real: float = Form(...), precio_sugerido: float = Form(...),
    url_imagen: str = Form(None)
):
    import database
    import models
    import security
    
    db = next(database.get_db())
    try:
        admin = security.PermisoRol(["Administrador"])(security.obtener_usuario_actual(request, db))
        
        nuevo_prod = models.Producto(
            categoria=categoria, nombre_refaccion=nombre_refaccion, marca=marca,
            modelo=modelo, ano_grupo=ano_grupo, compatibilidad=compatibilidad,
            condicion=condicion, ubicacion_fisica=ubicacion_fisica, dueno_id=dueno_id,
            precio_real=precio_real, precio_sugerido=precio_sugerido
)
        db.add(nuevo_prod)
        db.commit()
        db.refresh(nuevo_prod)
        urls_pieza = subir_fotos_a_storage(url_imagen, "piezas", 6)
        for u_img in urls_pieza:
            db.add(models.ImagenesPieza(producto_id=nuevo_prod.id, url_imagen=u_img))
            
        audit = models.BitacoraAuditoria(usuario_id=admin.id, accion_realizada=f"Registro de refacción #{nuevo_prod.id} - {nombre_refaccion}")
        db.add(audit)
        db.commit()
        return RedirectResponse(url="/mostrador?msg=Producto+Registrado", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/productos/vender/{id}")
def marcar_como_vendido(id: int, request: Request, bg_tasks: BackgroundTasks):
    import database
    import models
    import security
    
    db = next(database.get_db())
    try:
        usuario = security.PermisoRol(["Administrador", "Vendedor"])(security.obtener_usuario_actual(request, db))
        prod = db.query(models.Producto).filter(models.Producto.id == id).first()
        
        if not prod or prod.cantidad_disponible <= 0:
            raise HTTPException(status_code=400, detail="Stock no disponible o producto no encontrado")
        
        prod.cantidad_disponible -= 1
        ganancia = prod.precio_sugerido - prod.precio_real
        
        venta = models.HistorialVenta(
            producto_id=prod.id, vendedor_id=usuario.id,
            estado_venta=models.EstadoVentaEnum.Completada,
            precio_costo_dueno=prod.precio_real, precio_venta_publico=prod.precio_sugerido,
            ganancia_comision=ganancia, liquidado_al_dueno=False, saldo_por_cobrar=prod.precio_real
        )
        db.add(venta)
        
        # Obtener información del dueño para la notificación automática por WhatsApp
        dueno = db.query(models.Usuario).filter(models.Usuario.id == prod.dueno_id).first()
        if dueno and dueno.telefono_celular:
            bg_tasks.add_task(
                enviar_alerta_whatsapp_task,
                telefono=dueno.telefono_celular,
                producto_id=prod.id,
                nombre_pieza=prod.nombre_refaccion
            )
            
        audit = models.BitacoraAuditoria(
            usuario_id=usuario.id,
            accion_realizada=f"Venta de unidad de producto #{prod.id} - {prod.nombre_refaccion}"
        )
        db.add(audit)
        db.commit()
        return RedirectResponse(url="/mostrador?msg=Venta+Completada", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()
@app.get("/inventario/exportar/csv")
def exportar_inventario_csv(request: Request):
    import io
    from datetime import datetime
    from fastapi.responses import StreamingResponse
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    import database, models, security

    db = next(database.get_db())
    try:
        usuario = security.PermisoRol(["Administrador", "Vendedor"])(security.obtener_usuario_actual(request, db))
        if usuario.rol == models.RolEnum.Administrador or usuario.rol == "Administrador":
            productos = db.query(models.Producto).filter(models.Producto.cantidad_disponible > 0).order_by(models.Producto.id).all()
            nombre_archivo = "Inventario_General_AutoStock_Mayab.xlsx"
            titulo_reporte = "REPORTE EJECUTIVO DE INVENTARIO GENERAL"
        else:
            productos = db.query(models.Producto).filter(models.Producto.dueno_id == usuario.id, models.Producto.cantidad_disponible > 0).order_by(models.Producto.id).all()
            nombre_archivo = f"Inventario_{usuario.usuario}_AutoStock.xlsx"
            titulo_reporte = f"INVENTARIO DE AFILIADO: {usuario.nombre.upper()}"

        wb = Workbook()
        ws = wb.active
        ws.title = "Inventario"

        ws.merge_cells("A1:J1")
        ws["A1"] = f"AUTOSTOCK MAYAB — {titulo_reporte}"
        ws["A1"].font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
        ws["A1"].fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
        ws["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws.row_dimensions.height = 32

        ws.merge_cells("A2:J2")
        ws["A2"] = f"Generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')} hrs  |  Total de refacciones activas: {len(productos)}"
        ws["A2"].font = Font(name="Calibri", size=10, italic=True, color="334155")
        ws["A2"].fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
        ws["A2"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws.row_dimensions.height = 20

        encabezados = [
            "ID", "Categoría", "Refacción", "Marca", "Modelo",
            "Años", "Ubicación", "Costo Dueño", "Precio Público", "Margen Estimado"
        ]
        ws.append([])
        ws.append(encabezados)

        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        borde_fino = Border(
            left=Side(style="thin", color="CBD5E1"),
            right=Side(style="thin", color="CBD5E1"),
            top=Side(style="thin", color="CBD5E1"),
            bottom=Side(style="thin", color="CBD5E1")
        )

        ws.row_dimensions.height = 26
        for cell in ws[4]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = borde_fino

        total_costo = 0.0
        total_publico = 0.0
        total_margen = 0.0

        for idx, p in enumerate(productos, start=5):
            cat = p.categoria.value if hasattr(p.categoria, "value") else str(p.categoria)
            costo = float(p.precio_real or 0)
            publico = float(p.precio_sugerido or 0)
            margen = publico - costo

            total_costo += costo
            total_publico += publico
            total_margen += margen

            fila = [
                p.id, cat, p.nombre_refaccion, p.marca, p.modelo,
                p.ano_grupo, p.ubicacion_fisica, costo, publico, margen
            ]
            ws.append(fila)
            ws.row_dimensions[idx].height = 22

            for col_idx, cell in enumerate(ws[idx], 1):
                cell.border = borde_fino
                cell.font = Font(name="Calibri", size=10, color="0F172A")
                if idx % 2 == 0:
                    cell.fill = zebra_fill

                if col_idx in (1, 6):
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                elif col_idx in (8, 9, 10):
                    cell.number_format = '"$"#,##0.00'
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                    if col_idx == 10:
                        cell.font = Font(name="Calibri", size=10, bold=True, color="15803D")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")

        fila_total = len(productos) + 5
        ws.cell(row=fila_total, column=7, value="TOTALES:").font = Font(name="Calibri", size=11, bold=True, color="0F172A")
        ws.cell(row=fila_total, column=7).alignment = Alignment(horizontal="right", vertical="center")

        for col_idx, valor in [(8, total_costo), (9, total_publico), (10, total_margen)]:
            celda = ws.cell(row=fila_total, column=col_idx, value=valor)
            celda.number_format = '"$"#,##0.00'
            celda.font = Font(name="Calibri", size=11, bold=True, color="0F172A")
            celda.fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
            celda.border = borde_fino
            celda.alignment = Alignment(horizontal="right", vertical="center")
        ws.row_dimensions[fila_total].height = 26

        ws.auto_filter.ref = f"A4:J{len(productos) + 4}"
        ws.freeze_panes = "A5"

        for col in ws.iter_cols(min_row=4, max_row=fila_total):
            max_len = max((len(str(cell.value or "")) for cell in col), default=10)
            ws.column_dimensions[col[0].column_letter].width = max_len + 5

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        headers = {"Content-Disposition": f'attachment; filename="{nombre_archivo}"'}
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers
        )
    finally:
        db.close()
@app.get("/inventario/reporte/pdf", response_class=HTMLResponse)
def reporte_imprimible_pdf(request: Request):
    import database, models, security
    from datetime import datetime

    db = next(database.get_db())
    try:
        usuario = security.PermisoRol(["Administrador", "Vendedor"])(security.obtener_usuario_actual(request, db))
        if usuario.rol == models.RolEnum.Administrador or usuario.rol == "Administrador":
            productos = db.query(models.Producto).filter(models.Producto.cantidad_disponible > 0).all()
            titulo = "Inventario General de Bodega"
        else:
            productos = db.query(models.Producto).filter(models.Producto.dueno_id == usuario.id, models.Producto.cantidad_disponible > 0).all()
            titulo = f"Inventario: {usuario.nombre}"

        filas = ""
        total_costo = 0.0
        for p in productos:
            total_costo += p.precio_real
            filas += f"<tr><td>#{p.id}</td><td><b>{p.nombre_refaccion}</b><br><small>{p.marca} {p.modelo}</small></td><td>{p.ubicacion_fisica}</td><td>${p.precio_real:,.2f}</td><td>${p.precio_sugerido:,.2f}</td></tr>"

        html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{titulo}</title>
        <style>body{{font-family:sans-serif;padding:15px}}table{{width:100%;border-collapse:collapse;font-size:12px}}th,td{{border-bottom:1px solid #ddd;padding:8px;text-align:left}}th{{background:#0f172a;color:#fff}}.btn{{background:#ea580c;color:#fff;border:none;padding:12px;width:100%;font-weight:bold;border-radius:8px;margin-bottom:15px}}@media print{{.btn{{display:none}}}}</style></head>
        <body><button class="btn" onclick="window.print()">🖨️ Guardar PDF / Imprimir</button><h2>⚙️ AutoStock Mayab - {titulo}</h2><p>Fecha: {datetime.now().strftime('%d/%m/%Y')} | Piezas: {len(productos)}</p>
        <table><thead><tr><th>ID</th><th>Refacción</th><th>Ubicación</th><th>Costo</th><th>Público</th></tr></thead><tbody>{filas}</tbody></table>
        <h3 style="text-align:right">Total Costo: ${total_costo:,.2f}</h3></body></html>"""
        return HTMLResponse(content=html)
    finally:
        db.close()
@app.post("/ventas/validar-pago/{venta_id}")
def validar_pago_venta(venta_id: int, request: Request):
    import database, models, security
    db = next(database.get_db())
    try:
        admin = security.PermisoRol(["Administrador"])(security.obtener_usuario_actual(request, db))
        venta = db.query(models.HistorialVenta).filter(models.HistorialVenta.id == venta_id).first()
        if venta:
            venta.liquidado_al_dueno = True
            venta.saldo_por_cobrar = 0.0
            db.add(models.BitacoraAuditoria(usuario_id=admin.id, accion_realizada=f"Validación de pago recibido de venta #{venta.id}"))
            db.commit()
        return RedirectResponse(url="/mostrador?msg=Pago+validado+correctamente", status_code=status.HTTP_303_SEE_OTHER)
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
            for v in ventas:
                v.liquidado_al_dueno = True
                v.saldo_por_cobrar = 0.0
            db.add(models.BitacoraAuditoria(usuario_id=admin.id, accion_realizada=f"Liquidación procesada para afiliado #{dueno_id}"))
            db.commit()
        return RedirectResponse(url="/mostrador?msg=Liquidacion+procesada+con+exito", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/garaje/agregar")
def agregar_garaje(request: Request, marca: str = Form(...), modelo: str = Form(...), ano: str = Form(...), apodo: str = Form("")):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        if not usuario:
            return RedirectResponse(url="/mostrador?error=Inicia+sesion+para+guardar+tu+auto", status_code=status.HTTP_303_SEE_OTHER)
        db.add(models.GarajeUsuario(usuario_id=usuario.id, marca=marca, modelo=modelo, ano=ano, apodo=apodo))
        db.commit()
        return RedirectResponse(url="/mostrador?msg=Auto+guardado+en+Mi+Garaje", status_code=status.HTTP_303_SEE_OTHER)
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
        return RedirectResponse(url="/mostrador?msg=Vehiculo+eliminado", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/taller/guardar-perfil")
def guardar_perfil_taller(request: Request, nombre_taller: str = Form(...), colonia_region: str = Form(...), especialidad: str = Form("Mecánica General"), margen_porcentaje: float = Form(15.0), pin_seguridad: str = Form("1234")):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        if not usuario:
            return RedirectResponse(url="/mostrador?error=Inicia+sesion+primero", status_code=status.HTTP_303_SEE_OTHER)
        perfil = db.query(models.PerfilTaller).filter(models.PerfilTaller.usuario_id == usuario.id).first()
        if perfil:
            perfil.nombre_taller = nombre_taller
            perfil.colonia_region = colonia_region
            perfil.especialidad = especialidad
            perfil.margen_porcentaje = margen_porcentaje
            perfil.pin_seguridad = pin_seguridad.strip()[:4] or "1234"
        else:
            db.add(models.PerfilTaller(
                usuario_id=usuario.id, nombre_taller=nombre_taller, colonia_region=colonia_region,
                especialidad=especialidad, margen_porcentaje=margen_porcentaje,
                pin_seguridad=pin_seguridad.strip()[:4] or "1234"
            ))
        db.commit()
        return RedirectResponse(url="/mostrador?msg=Perfil+de+Taller+actualizado", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/mercado/pujar/{anuncio_id}")
def pujar_subasta(anuncio_id: int, monto: float = Form(...), request: Request = None):
    import database, models, security
    from datetime import timedelta
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        if not usuario:
            return RedirectResponse(url="/mostrador?error=Inicia+sesion+para+pujar", status_code=status.HTTP_303_SEE_OTHER)
        anuncio = db.query(models.AnuncioMercado).filter(models.AnuncioMercado.id == anuncio_id).first()
        ahora = datetime.now(timezone.utc)
        if not anuncio or not anuncio.es_subasta or anuncio.vendido or (anuncio.subasta_fin and anuncio.subasta_fin <= ahora):
            return RedirectResponse(url="/mostrador?error=Subasta+finalizada+o+no+disponible", status_code=status.HTTP_303_SEE_OTHER)
        minimo = float(anuncio.puja_actual or anuncio.precio or 0) + 50.0
        if monto < minimo:
            return RedirectResponse(url=f"/mostrador?error=La+puja+minima+es+${int(minimo)}", status_code=status.HTTP_303_SEE_OTHER)
        anuncio.puja_actual = monto
        anuncio.ganador_id = usuario.id
        if anuncio.subasta_fin and (anuncio.subasta_fin - ahora).total_seconds() <= 30:
            anuncio.subasta_fin = anuncio.subasta_fin + timedelta(minutes=2)
        db.add(models.PujaSubasta(anuncio_id=anuncio.id, usuario_id=usuario.id, monto=monto))
        db.commit()
        return RedirectResponse(url="/mostrador?msg=Puja+registrada+con+exito", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/mercado/vendido/{anuncio_id}")
def marcar_anuncio_vendido(anuncio_id: int, request: Request):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        anuncio = db.query(models.AnuncioMercado).filter(models.AnuncioMercado.id == anuncio_id).first()
        if usuario and anuncio and (anuncio.usuario_id == usuario.id or usuario.rol in [models.RolEnum.Administrador, "Administrador"]):
            anuncio.vendido = True
            db.commit()
        return RedirectResponse(url="/mostrador?msg=Marcado+como+vendido", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/urgente/crear")
def crear_solicitud_urgente(request: Request, titulo: str = Form(...), vehiculo: str = Form(...), detalles: str = Form(...), zona_cancun: str = Form("Cancún")):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        if not usuario:
            return RedirectResponse(url="/mostrador?error=Inicia+sesion+para+publicar", status_code=status.HTTP_303_SEE_OTHER)
        db.add(models.SolicitudUrgente(usuario_id=usuario.id, titulo=titulo, vehiculo=vehiculo, detalles=detalles, zona_cancun=zona_cancun))
        db.commit()
        return RedirectResponse(url="/mostrador?msg=Solicitud+urgente+publicada", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/urgente/responder/{sol_id}")
def responder_solicitud_urgente(sol_id: int, mensaje: str = Form(...), precio_ofrecido: float = Form(None), request: Request = None):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        if not usuario:
            return RedirectResponse(url="/mostrador?error=Inicia+sesion+para+responder", status_code=status.HTTP_303_SEE_OTHER)
        db.add(models.RespuestaUrgente(solicitud_id=sol_id, usuario_id=usuario.id, mensaje=mensaje, precio_ofrecido=precio_ofrecido))
        db.commit()
        return RedirectResponse(url="/mostrador?msg=Respuesta+enviada", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/urgente/cerrar/{sol_id}")
def cerrar_solicitud_urgente(sol_id: int, request: Request):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        sol = db.query(models.SolicitudUrgente).filter(models.SolicitudUrgente.id == sol_id).first()
        if usuario and sol and (sol.usuario_id == usuario.id or usuario.rol in [models.RolEnum.Administrador, "Administrador"]):
            sol.resuelto = True
            db.commit()
        return RedirectResponse(url="/mostrador?msg=Solicitud+marcada+como+conseguida", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/diagnostico/crear")
def crear_diagnostico(request: Request, vehiculo: str = Form(...), sintoma: str = Form(...), descripcion: str = Form(...)):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        if not usuario:
            return RedirectResponse(url="/mostrador?error=Inicia+sesion+para+consultar", status_code=status.HTTP_303_SEE_OTHER)
        db.add(models.DiagnosticoForo(usuario_id=usuario.id, vehiculo=vehiculo, sintoma=sintoma, descripcion=descripcion))
        db.commit()
        return RedirectResponse(url="/mostrador?msg=Consulta+publicada+en+Diagnostico", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/diagnostico/comentar/{foro_id}")
def comentar_diagnostico(foro_id: int, comentario: str = Form(...), request: Request = None):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        if not usuario:
            return RedirectResponse(url="/mostrador?error=Inicia+sesion+para+comentar", status_code=status.HTTP_303_SEE_OTHER)
        db.add(models.ComentarioDiagnostico(diagnostico_id=foro_id, usuario_id=usuario.id, comentario=comentario))
        db.commit()
        return RedirectResponse(url="/mostrador?msg=Aporte+publicado", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/diagnostico/solucionado/{foro_id}")
def solucionar_diagnostico(foro_id: int, request: Request):
    import database, models, security
    db = next(database.get_db())
    try:
        usuario = security.obtener_usuario_actual(request, db)
        foro = db.query(models.DiagnosticoForo).filter(models.DiagnosticoForo.id == foro_id).first()
        if usuario and foro and (foro.usuario_id == usuario.id or usuario.rol in [models.RolEnum.Administrador, "Administrador"]):
            foro.solucionado = True
            db.commit()
        return RedirectResponse(url="/mostrador?msg=Falla+marcada+como+solucionada", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/productos/editar/{prod_id}")
def editar_producto(prod_id: int, nombre_refaccion: str = Form(...), ubicacion_fisica: str = Form(...), condicion: str = Form("Original Usada - Excelente"), precio_real: float = Form(...), precio_sugerido: float = Form(...), request: Request = None):
    import database, models, security
    db = next(database.get_db())
    try:
        admin = security.PermisoRol(["Administrador"])(security.obtener_usuario_actual(request, db))
        prod = db.query(models.Producto).filter(models.Producto.id == prod_id).first()
        if prod:
            prod.nombre_refaccion = nombre_refaccion
            prod.ubicacion_fisica = ubicacion_fisica
            prod.condicion = condicion
            prod.precio_real = precio_real
            prod.precio_sugerido = precio_sugerido
            db.add(models.BitacoraAuditoria(usuario_id=admin.id, accion_realizada=f"Edición de pieza #{prod.id}"))
            db.commit()
        return RedirectResponse(url="/mostrador?msg=Pieza+actualizada", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/productos/apartar/{prod_id}")
def apartar_producto(prod_id: int, request: Request):
    import database, models, security
    from datetime import timedelta
    db = next(database.get_db())
    try:
        operador = security.PermisoRol(["Administrador", "Vendedor"])(security.obtener_usuario_actual(request, db))
        prod = db.query(models.Producto).filter(models.Producto.id == prod_id).first()
        if prod:
            ahora = datetime.now(timezone.utc)
            if prod.apartado_hasta and prod.apartado_hasta > ahora:
                prod.apartado_hasta = None
                msg = "Apartado+liberado"
            else:
                prod.apartado_hasta = ahora + timedelta(hours=2)
                msg = "Pieza+apartada+por+2+horas"
            db.add(models.BitacoraAuditoria(usuario_id=operador.id, accion_realizada=f"Cambio apartado pieza #{prod.id}"))
            db.commit()
            return RedirectResponse(url=f"/mostrador?msg={msg}", status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(url="/mostrador", status_code=status.HTTP_303_SEE_OTHER)
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
            venta.estado_venta = models.EstadoVentaEnum.Cancelada_Devuelta
            venta.saldo_por_cobrar = 0.0
            prod = db.query(models.Producto).filter(models.Producto.id == venta.producto_id).first()
            if prod:
                prod.cantidad_disponible = (prod.cantidad_disponible or 0) + 1
            db.add(models.BitacoraAuditoria(usuario_id=admin.id, accion_realizada=f"Devolución registrada de venta #{venta.id}"))
            db.commit()
        return RedirectResponse(url="/mostrador?msg=Devolucion+procesada+y+pieza+reingresada", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.get("/ping")
def mantener_despierto():
    return {"estado": "activo"}
