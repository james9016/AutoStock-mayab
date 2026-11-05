import json
from fastapi import FastAPI, Depends, Request, Form, HTTPException, status, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import database
import models
import security
import seed

app = FastAPI(title="AutoStock Mayab")

models.Base.metadata.create_all(bind=database.engine)

@app.on_event("startup")
def on_startup():
    db = next(database.get_db())
    try:
        seed.seed_database(db)
    finally:
        db.close() # Garantiza liberar de inmediato la conexión abierta en Supabase

# Configuración de carpetas de recursos y plantillas
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except:
    pass

templates = Jinja2Templates(directory="templates")

async def enviar_alerta_whatsapp_task(telefono: str, producto_id: int, nombre_pieza: str):
    print(f"[WHATSAPP API MOCK] Notificación enviada al dueño ({telefono}): La pieza #{producto_id} ({nombre_pieza}) se ha marcado como vendida.")

@app.get("/", response_class=HTMLResponse)
@app.get("/mostrador", response_class=HTMLResponse)
def vista_mostrador(request: Request, db: Session = Depends(database.get_db)):
    usuario = security.obtener_usuario_actual(request, db)
    productos = db.query(models.Producto).filter(models.Producto.cantidad_disponible > 0).all()
    usuarios_sistema = db.query(models.Usuario).all()
    
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
        "productos": productos, 
        "usuarios": usuarios_sistema,
        "dict_vehiculos": json.dumps(seed.DICCIONARIO_VEHICULOS),
        "liquidaciones": liquidaciones_pendientes
    })

@app.post("/auth/login")
def login(usuario: str = Form(...), contrasena: str = Form(...), db: Session = Depends(database.get_db)):
    user = db.query(models.Usuario).filter(models.Usuario.usuario == usuario).first()
    if not user or not security.verificar_password(contrasena, user.contrasena_hash):
        return RedirectResponse(url="/mostrador?error=Credenciales+Incorrectas", status_code=status.HTTP_303_SEE_OTHER)
    if user.rol == models.RolEnum.Publico_General:
        return RedirectResponse(url="/mostrador?error=Acceso+Denegado+Bodega", status_code=status.HTTP_303_SEE_OTHER)
    
    token = security.crear_token_acceso(data={"sub": user.usuario})
    response = RedirectResponse(url="/mostrador", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True)
    return response

@app.get("/auth/logout")
def logout():
    response = RedirectResponse(url="/mostrador", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response

@app.post("/productos/crear")
def registrar_producto(
    request: Request,
    categoria: str = Form(...), nombre_refaccion: str = Form(...),
    marca: str = Form(...), modelo: str = Form(...), ano_grupo: str = Form(...),
    compatibilidad: str = Form(None), ubicacion_fisica: str = Form(...),
    dueno_id: int = Form(...), precio_real: float = Form(...),
    precio_sugerido: float = Form(...), url_imagen: str = Form(None),
    db: Session = Depends(database.get_db)
):
    admin = security.requerir_rol(["Administrador"])(security.obtener_usuario_actual(request, db))
    
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

@app.post("/productos/vender/{id}")
def marcar_como_vendido(id: int, request: Request, bg_tasks: BackgroundTasks, db: Session = Depends(database.get_db)):
    usuario = security.requerir_rol(["Administrador", "Vendedor"])(security.obtener_usuario_actual(request, db))
    prod = db.query(models.Producto).filter(models.Producto.id == id).first()
    
    if not prod or prod.cantidad_disponible <= 0:
        raise HTTPException(status_code=400, detail="Stock no disponible")
    
    prod.cantidad_disponible -= 1
    ganancia = prod.precio_sugerido - prod.precio_real
    
    venta = models.HistorialVenta(
        producto_id=prod.id, vendedor_id=usuario.id,
        estado_venta=models.EstadoVentaEnum.Completada,
        precio_costo_dueno=prod.precio_real, precio_venta_publico=prod.precio_sugerido,
        ganancia_comision=ganancia, liquidado_al_dueno=False, saldo_por_cobrar=prod.precio_real
    )
    db.add(venta)
    
    audit = models.BitacoraAuditoria(usuario_id=usuario.id, accion_realizada=f"Venta de unidad de producto #{prod.id}")
    db.add(audit)
    db.commit()
    
    dueno = db.query(models.Usuario).filter(models.Usuario.id == prod.dueno_id).first()
    if dueno and dueno.telefono_celular:
        bg_tasks.add_task(enviar_alerta_whatsapp_task, dueno.telefono_celular, prod.id, prod.nombre_refaccion)
        
    return RedirectResponse(url="/mostrador?msg=Venta+Registrada+Exitosamente", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/liquidaciones/procesar/{dueno_id}")
def procesar_liquidacion(dueno_id: int, request: Request, ids_ventas: str = Form(...), db: Session = Depends(database.get_db)):
    admin = security.requerir_rol(["Administrador"])(security.obtener_usuario_actual(request, db))
    lista_ids = [int(x) for x in ids_ventas.split(",") if x]
    
    db.query(models.HistorialVenta).filter(models.HistorialVenta.id.in_(lista_ids)).update(
        {models.HistorialVenta.liquidado_al_dueno: True, models.HistorialVenta.saldo_por_cobrar: 0.0},
        synchronize_session=False
    )
    
    audit = models.BitacoraAuditoria(usuario_id=admin.id, accion_realizada=f"Corte y liquidación procesada al dueño ID {dueno_id}")
    db.add(audit)
    db.commit()
    return RedirectResponse(url="/mostrador?msg=Liquidacion+Completada", status_code=status.HTTP_303_SEE_OTHER)
