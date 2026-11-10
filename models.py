import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum, event, DDL
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class RolEnum(str, enum.Enum):
    Administrador = "Administrador"
    Vendedor = "Vendedor"
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
    Completada = "Completada"
    Cancelada_Devuelta = "Cancelada/Devuelta"

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    usuario = Column(String, unique=True, nullable=False, index=True)
    contrasena_hash = Column(String, nullable=False)
    rol = Column(Enum(RolEnum, native_enum=False), nullable=False)
    telefono_celular = Column(String, nullable=False)
    # ✅ Función lambda con timezone.utc para mantener la consistencia del servidor
    fecha_registro = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relaciones
    productos = relationship("Producto", back_populates="dueno")
    ventas = relationship("HistorialVenta", back_populates="vendedor")
    lista_espera = relationship("ListaEspera", back_populates="vendedor")
    auditorias = relationship("BitacoraAuditoria", back_populates="usuario")

class Producto(Base):
    __tablename__ = "productos"
    id = Column(Integer, primary_key=True, index=True)
    categoria = Column(Enum(CategoriaEnum, native_enum=False), nullable=False)
    nombre_refaccion = Column(String, nullable=False, index=True)
    marca = Column(String, nullable=False, index=True)
    modelo = Column(String, nullable=False, index=True)
    ano_grupo = Column(String, nullable=False)
    compatibilidad = Column(String, nullable=True)
    cantidad_disponible = Column(Integer, default=1, nullable=False)
    ubicacion_fisica = Column(String, nullable=False)
    dueno_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    precio_real = Column(Float, nullable=False)
    precio_sugerido = Column(Float, nullable=False)
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

# BLINDAJE LOGÍSTICO
# Modifica la secuencia de PostgreSQL para arrancar folios de productos desde 1000
event.listen(
    Producto.__table__,
    "after_create",
    DDL("ALTER SEQUENCE productos_id_seq RESTART WITH 1000;").execute_if(dialect="postgresql")
)
