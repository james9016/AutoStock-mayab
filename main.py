@app.post("/productos/vender/{id}")
def marcar_como_vendido(id: int, request: Request, bg_tasks: BackgroundTasks, db: Session = Depends(database.get_db)):
    usuario = security.requerir_rol(["Administrador", "Vendedor"])(security.obtener_usuario_actual(request, db))
    prod = db.query(models.Producto).filter(models.Producto.id == id).first()
    
    if not prod or prod.cantidad_disponible <= 0:
        raise HTTPException(status_code=400, detail="Stock no disponible o producto no encontrado")
    
    prod.cantidad_disponible -= 1
    ganancia = prod.precio_sugerido - prod.precio_real
    
    # Registrar la venta en el historial
    venta = models.HistorialVenta(
        producto_id=prod.id, 
        vendedor_id=usuario.id,
        estado_venta=models.EstadoVentaEnum.Completada,
        precio_costo_dueno=prod.precio_real, 
        precio_venta_publico=prod.precio_sugerido,
        ganancia_comision=ganancia, 
        liquidado_al_dueno=False, 
        saldo_por_cobrar=prod.precio_real
    )
    db.add(venta)
    
    # Registrar la acción en la bitácora de auditoría
    audit = models.BitacoraAuditoria(
        usuario_id=usuario.id, 
        accion_realizada=f"Venta de unidad de producto #{prod.id} - {prod.nombre_refaccion}"
    )
    db.add(audit)
    
    # Confirmar todos los cambios en la base de datos
    db.commit()
    
    # Si el dueño del producto tiene un teléfono registrado, disparamos la alerta en segundo plano
    dueno = db.query(models.Usuario).filter(models.Usuario.id == prod.dueno_id).first()
    if dueno and dueno.telefono_celular:
        bg_tasks.add_task(
            enviar_alerta_whatsapp_task, 
            telefono=dueno.telefono_celular, 
            producto_id=prod.id, 
            nombre_pieza=prod.nombre_refaccion
        )
        
    return RedirectResponse(url="/mostrador?msg=Venta+Registrada+Exitosamente", status_code=status.HTTP_303_SEE_OTHER)
