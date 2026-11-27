import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum, event, DDL
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class RolEnum(str, enum.Enum):
    Administrador = "Administrador"
    Vendedor = "Vendedor"
    Mecanico = "Mecanico"
    Publico_General = "Publico_General"

class CategoriaEnum(str, enum.Enum):
    carroceria = "Carrocería y Colisión"
    iluminacion = "Iluminación"
    motor = "Motor y Componentes"
    accesorios = "Accesorios de Motor"
    transmision = "Transmisión y Tren Motriz"
    suspension = "Suspensión y Dirección"
    frenos = "Sistema de Frenos"
    enfriamiento = "Enfriamiento y Calefacción"
    escape = "Escape y Combustible"
    electrica = "Eléctrica y Módulos"
    interiores = "Interiores y Plásticos"
    cristales = "Cristales y Vidrios"
    llantas = "Llantas y Rines"
    seguridad = "Seguridad (Airbags)"
    audio = "Audio e Infoentretenimiento"

class EstadoVentaEnum(str, enum.Enum):
    Pendiente = "Pendiente"
    Completada = "Completada"
    Cancelada_Devuelta = "Cancelada/Devuelta"

class CategoriaMercadoEnum(str, enum.Enum):
    autos = "Autos para Reparar / Chocadas"
    herramientas = "Herramientas y Equipo de Taller"
    rines_llantas = "Rines, Llantas y Accesorios"
    busco_pieza = "Busco Pieza (Solicitud)"

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    usuario = Column(String, unique=True, nullable=False, index=True)
    contrasena_hash = Column(String, nullable=False)
    rol = Column(Enum(RolEnum, native_enum=False), nullable=False)
    telefono_celular = Column(String, nullable=False)
    fecha_registro = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relaciones
    productos = relationship("Producto", back_populates="dueno")
    ventas = relationship("HistorialVenta", back_populates="vendedor")
    lista_espera = relationship("ListaEspera", back_populates="vendedor")
    auditorias = relationship("BitacoraAuditoria", back_populates="usuario")
    anuncios = relationship("AnuncioMercado", back_populates="autor", cascade="all, delete-orphan")
    garaje = relationship("GarajeUsuario", back_populates="usuario", cascade="all, delete-orphan")
    perfil_taller = relationship("PerfilTaller", back_populates="usuario", uselist=False, cascade="all, delete-orphan")
   
class Producto(Base):
    __tablename__ = "productos"
    id = Column(Integer, primary_key=True, index=True)
    categoria = Column(Enum(CategoriaEnum, native_enum=False), nullable=False)
    nombre_refaccion = Column(String, nullable=False, index=True)
    marca = Column(String, nullable=False, index=True)
    modelo = Column(String, nullable=False, index=True)
    ano_grupo = Column(String, nullable=False)
    compatibilidad = Column(String, nullable=True)
    condicion = Column(String, nullable=False, default="Original Usada - Excelente")
    cantidad_disponible = Column(Integer, default=1, nullable=False)
    ubicacion_fisica = Column(String, nullable=False)
    dueno_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    precio_real = Column(Float, nullable=False)
    precio_sugerido = Column(Float, nullable=False)
    apartado_hasta = Column(DateTime, nullable=True)
    fecha_ingreso = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relaciones
    dueno = relationship("Usuario", back_populates="productos")
    imagenes = relationship("ImagenesPieza", back_populates="producto", cascade="all, delete-orphan")
    ventas = relationship("HistorialVenta", back_populates="producto")

class ImagenesPieza(Base):
    __tablename__ = "imagenes_pieza"
    id = Column(Integer, primary_key=True, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    url_imagen = Column(String, nullable=False)
    
    # Relaciones
    producto = relationship("Producto", back_populates="imagenes")

class HistorialVenta(Base):
    __tablename__ = "historial_ventas"
    id = Column(Integer, primary_key=True, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    vendedor_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    fecha_venta = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    estado_venta = Column(Enum(EstadoVentaEnum, native_enum=False), nullable=False)
    precio_costo_dueno = Column(Float, nullable=False)
    precio_venta_publico = Column(Float, nullable=False)
    ganancia_comision = Column(Float, nullable=False)
    liquidado_al_dueno = Column(Boolean, default=False, nullable=False)
    saldo_por_cobrar = Column(Float, nullable=False)

    # Relaciones
    producto = relationship("Producto", back_populates="ventas")
    vendedor = relationship("Usuario", back_populates="ventas")

class ListaEspera(Base):
    __tablename__ = "lista_espera"
    id = Column(Integer, primary_key=True, index=True)
    refaccion_buscada = Column(String, nullable=False)
    vendedor_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    fecha_registro = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relaciones
    vendedor = relationship("Usuario", back_populates="lista_espera")

class BitacoraAuditoria(Base):
    __tablename__ = "bitacora_auditoria"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    accion_realizada = Column(String, nullable=False)
    fecha_hora = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relaciones
    usuario = relationship("Usuario", back_populates="auditorias")
    
class AnuncioMercado(Base):
    __tablename__ = "anuncios_mercado"
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, nullable=False, index=True)
    categoria = Column(Enum(CategoriaMercadoEnum, native_enum=False), nullable=False)
    precio = Column(Float, nullable=False, default=0.0)
    descripcion = Column(String, nullable=False)
    zona_cancun = Column(String, nullable=False, default="Cancún Centro")
    url_imagen = Column(String, nullable=True)
    vendido = Column(Boolean, default=False, nullable=False)
    es_subasta = Column(Boolean, default=False, nullable=False)
    subasta_fin = Column(DateTime, nullable=True)
    puja_actual = Column(Float, default=0.0, nullable=False)
    ganador_id = Column(Integer, nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    fecha_publicacion = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relaciones
    autor = relationship("Usuario", back_populates="anuncios")
    pujas = relationship("PujaSubasta", back_populates="anuncio", cascade="all, delete-orphan")

class PujaSubasta(Base):
    __tablename__ = "pujas_subasta"
    id = Column(Integer, primary_key=True, index=True)
    anuncio_id = Column(Integer, ForeignKey("anuncios_mercado.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    monto = Column(Float, nullable=False)
    fecha_puja = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    anuncio = relationship("AnuncioMercado", back_populates="pujas")

class GarajeUsuario(Base):
    __tablename__ = "garaje_usuarios"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    marca = Column(String, nullable=False)
    modelo = Column(String, nullable=False)
    ano = Column(String, nullable=False)
    apodo = Column(String, nullable=True)

    usuario = relationship("Usuario", back_populates="garaje")

class PerfilTaller(Base):
    __tablename__ = "perfiles_taller"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), unique=True, nullable=False)
    nombre_taller = Column(String, nullable=False)
    colonia_region = Column(String, nullable=False)
    especialidad = Column(String, nullable=False, default="Mecánica General")
    margen_porcentaje = Column(Float, nullable=False, default=15.0)
    pin_seguridad = Column(String, nullable=False, default="1234")

    usuario = relationship("Usuario", back_populates="perfil_taller")

class SolicitudUrgente(Base):
    __tablename__ = "solicitudes_urgentes"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    titulo = Column(String, nullable=False)
    vehiculo = Column(String, nullable=False)
    detalles = Column(String, nullable=False)
    zona_cancun = Column(String, nullable=False, default="Cancún")
    resuelto = Column(Boolean, default=False, nullable=False)
    fecha_creacion = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    respuestas = relationship("RespuestaUrgente", back_populates="solicitud", cascade="all, delete-orphan")

class RespuestaUrgente(Base):
    __tablename__ = "respuestas_urgentes"
    id = Column(Integer, primary_key=True, index=True)
    solicitud_id = Column(Integer, ForeignKey("solicitudes_urgentes.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    mensaje = Column(String, nullable=False)
    precio_ofrecido = Column(Float, nullable=True)
    fecha_respuesta = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    solicitud = relationship("SolicitudUrgente", back_populates="respuestas")

class DiagnosticoForo(Base):
    __tablename__ = "diagnosticos_foro"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    vehiculo = Column(String, nullable=False)
    sintoma = Column(String, nullable=False)
    descripcion = Column(String, nullable=False)
    solucionado = Column(Boolean, default=False, nullable=False)
    fecha_creacion = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    comentarios = relationship("ComentarioDiagnostico", back_populates="diagnostico", cascade="all, delete-orphan")

class ComentarioDiagnostico(Base):
    __tablename__ = "comentarios_diagnostico"
    id = Column(Integer, primary_key=True, index=True)
    diagnostico_id = Column(Integer, ForeignKey("diagnosticos_foro.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    comentario = Column(String, nullable=False)
    fecha_comentario = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    diagnostico = relationship("DiagnosticoForo", back_populates="comentarios")

# BLINDAJE LOGÍSTICO
# Modifica la secuencia de PostgreSQL para arrancar folios de productos desde 1000
event.listen(
    Producto.__table__,
    "after_create",
    DDL("ALTER SEQUENCE productos_id_seq RESTART WITH 1000;").execute_if(dialect="postgresql")
    )

