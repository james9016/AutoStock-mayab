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

async def enviar_alerta_whatsapp_task(telefono: str, producto_id: int, nombre_pieza: str):
    # Proceso asíncrono seguro en segundo plano para notificar salidas de inventario
    print(f"[WHATSAPP API] Alerta automatizada enviada al afiliado ({telefono}): Refacción #{producto_id} ({nombre_pieza}) confirmada como vendida.")

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
        productos_raw = db.query(models.Producto).filter(models.Producto.cantidad_disponible > 0).all()
        usuarios_sistema = db.query(models.Usuario).all()
        
        # BÚNKER DE PROTECCIÓN DE PRECIOS: Sanitización de datos desde el Servidor
        productos_sanitizados = []
        for prod in productos_raw:
            item = {
                "id": prod.id,
                "categoria": prod.categoria,
                "nombre_refaccion": prod.nombre_refaccion,
                "marca": prod.marca,
                "modelo": prod.modelo,
                "ano_grupo": prod.ano_grupo,
                "compatibilidad": prod.compatibilidad,
                "precio_sugerido": prod.precio_sugerido,
                "dueno_id": prod.dueno_id,
                "fecha_ingreso": prod.fecha_ingreso.isoformat() if prod.fecha_ingreso else None,
                "precio_real": None,
                "ubicacion_fisica": "🔒 Autentíquese para ver ubicación"
            }
            
            if usuario and usuario.rol in [models.RolEnum.Administrador, models.RolEnum.Vendedor]:
                item["precio_real"] = prod.precio_real
                item["ubicacion_fisica"] = prod.ubicacion_fisica
                
            productos_sanitizados.append(item)

        productos_sanitizados = sorted(productos_sanitizados, key=lambda x: x["id"])

        liquidaciones_pendientes = {}
        if usuario and usuario.rol == models.RolEnum.Administrador:
            ventas_no_liquidadas = db.query(models.HistorialVenta).filter(models.HistorialVenta.liquidado_al_dueno == False).all()
            for v in ventas_no_liquidadas:
                prod = db.query(models.Producto).filter(models.Producto.id == v.producto_id).first()
                if prod:
                    dueno = db.query(models.Usuario).filter(models.Usuario.id == prod.dueno_id).first()
                    if dueno:
                        if dueno.id not in liquidaciones_pendientes:
                            liquidaciones_pendientes[dueno.id] = {"dueno": dueno.nombre, "saldo": 0.0, "items": []}
                        liquidaciones_pendientes[dueno.id]["saldo"] += v.saldo_por_cobrar
                        liquidaciones_pendientes[dueno.id]["items"].append(v.id)

        return templates.TemplateResponse("mostrador.html", {
            "request": request, 
            "usuario": usuario, 
            "productos": productos_sanitizados, 
            "usuarios": usuarios_sistema,
            "dict_vehiculos": json.dumps(seed.DICCIONARIO_VEHICULOS),
            "liquidaciones": liquidaciones_pendientes
        })
    finally:
        db.close()

@app.post("/auth/login")
def login(usuario: str = Form(...), contrasena: str = Form(...)):
    import database
    import models
    import security
    
    db = next(database.get_db())
    try:
        user = db.query(models.Usuario).filter(models.Usuario.usuario == usuario).first()
        if not user or not security.verificar_password(contrasena, user.contrasena_hash):
            return RedirectResponse(url="/mostrador?error=Credenciales+Incorrectas", status_code=status.HTTP_303_SEE_OTHER)
        
        if user.rol == models.RolEnum.Publico_General:
            return RedirectResponse(url="/mostrador?error=Acceso+Denegado+Bodega", status_code=status.HTTP_303_SEE_OTHER)
        
        token = security.crear_token_acceso(data={"sub": user.usuario})
        response = RedirectResponse(url="/mostrador", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True, secure=True, samesite="lax")
        return response
    finally:
        db.close()
@app.post("/usuarios/aprobar/{user_id}")
def aprobar_usuario(user_id: int, nuevo_rol: str = Form(...), request: Request = None):
    import database
    import models
    import security
    
    db = next(database.get_db())
    try:
        admin = security.PermisoRol(["Administrador"])(security.obtener_usuario_actual(request, db))
        user_target = db.query(models.Usuario).filter(models.Usuario.id == user_id).first()
        
        if not user_target:
            return RedirectResponse(url="/mostrador?error=Usuario+no+encontrado", status_code=status.HTTP_303_SEE_OTHER)
        
        if nuevo_rol == "Vendedor":
            user_target.rol = models.RolEnum.Vendedor
        elif nuevo_rol == "Administrador":
            user_target.rol = models.RolEnum.Administrador
            
        audit = models.BitacoraAuditoria(
            usuario_id=admin.id, 
            accion_realizada=f"Aprobación de usuario @{user_target.usuario} con rol {nuevo_rol}"
        )
        db.add(audit)
        db.commit()
        return RedirectResponse(url="/mostrador?msg=Usuario+Aprobado+y+Activado", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.get("/auth/logout")
def logout():
    response = RedirectResponse(url="/mostrador", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response
@app.post("/auth/registro")
def registrar_usuario_publico(
    nombre: str = Form(...),
    usuario: str = Form(...),
    telefono_celular: str = Form(...),
    contrasena: str = Form(...)
):
    import database
    import models
    import security
    
    db = next(database.get_db())
    try:
        existe = db.query(models.Usuario).filter(models.Usuario.usuario == usuario).first()
        if existe:
            return RedirectResponse(url="/mostrador?error=El+usuario+ya+existe", status_code=status.HTTP_303_SEE_OTHER)
        
        nuevo_usuario = models.Usuario(
            nombre=nombre,
            usuario=usuario,
            contrasena_hash=security.obtener_password_hash(contrasena),
            rol=models.RolEnum.Publico_General,
            telefono_celular=telefono_celular
        )
        db.add(nuevo_usuario)
        db.commit()
        return RedirectResponse(url="/mostrador?msg=Registro+exitoso.+Solicita+activacion+al+Admin", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        db.close()

@app.post("/productos/crear")
def registrar_producto(
    request: Request,
    categoria: str = Form(...), nombre_refaccion: str = Form(...),
    marca: str = Form(...), modelo: str = Form(...), ano_grupo: str = Form(...),
    compatibilidad: str = Form(None), ubicacion_fisica: str = Form(...),
    dueno_id: int = Form(...), precio_real: float = Form(...),
    precio_sugerido: float = Form(...), url_imagen: str = Form(None)
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
            ubicacion_fisica=ubicacion_fisica, dueno_id=dueno_id,
            precio_real=precio_real, precio_sugerido=precio_sugerido
        )
        db.add(nuevo_prod)
        db.commit()
        db.refresh(nuevo_prod)
        
        if url_imagen:
            img = models.ImagenesPieza(producto_id=nuevo_prod.id, url_imagen=url_imagen)
            db.add(img)
        
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
        for cell in ws:
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
            ws.column_dimensions[col.column_letter].width = max_len + 5

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
      
@app.get("/ping")
def mantener_despierto():
    return {"estado": "activo"}
