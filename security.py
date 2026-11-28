import os
import secrets
import bcrypt
from fastapi import Request, HTTPException, Depends, status
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
import database
import models

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if os.getenv("RENDER") or os.getenv("HTTPS") == "1":
        raise RuntimeError("CRÍTICO: Falta la variable de entorno SECRET_KEY en producción.")
    SECRET_KEY = secrets.token_hex(32)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480

def obtener_password_hash(password: str) -> str:
    password_bytes = password[:72].encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")

def verificar_password(plain_password: str, hashed_password: str) -> bool:
    try:
        password_bytes = plain_password[:72].encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False

def _firma_sesion(usuario: models.Usuario) -> str:
    return (usuario.contrasena_hash or "")[-12:]

def crear_token_acceso(data: dict, usuario: models.Usuario | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    if usuario is not None:
        to_encode["sig"] = _firma_sesion(usuario)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def es_entorno_seguro(request: Request) -> bool:
    if os.getenv("RENDER") or os.getenv("HTTPS") == "1":
        return True
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    return proto == "https"

def obtener_usuario_actual(request: Request, db: Session = Depends(database.get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        if token.startswith("Bearer "):
            token = token.split(" ", 1).strip()
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        sig_token: str | None = payload.get("sig")
        if not username:
            return None
    except JWTError:
        return None

    user = db.query(models.Usuario).filter(models.Usuario.usuario == username.strip().lower()).first()
    if not user:
        return None
    if sig_token and sig_token != _firma_sesion(user):
        return None
    return user

class PermisoRol:
    def __init__(self, roles_permitidos: list[str]):
        self.roles_permitidos = roles_permitidos

    def __call__(self, usuario: models.Usuario = Depends(obtener_usuario_actual)):
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No autenticado. Por favor inicie sesión."
            )
        rol_val = usuario.rol.value if hasattr(usuario.rol, "value") else str(usuario.rol)
        if rol_val not in self.roles_permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado. Permisos insuficientes para esta operación comercial."
            )
        return usuario
    
