import os
from fastapi import Request, HTTPException, Depends, status
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import database
import models

# Llave secreta para firmar los tokens de sesión de los operadores
SECRET_KEY = os.getenv("SECRET_KEY", "SUPER_SECRET_COMP_MAYA_2026_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # Duración de una jornada laboral completa (8 horas)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def obtener_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verificar_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def crear_token_acceso(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def obtener_usuario_actual(request: Request, db = Depends(database.get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        if token.startswith("Bearer "):
            token = token.split(" ")[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None
    usuario = db.query(models.Usuario).filter(models.Usuario.usuario == username).first()
    return usuario

def requerir_rol(roles_permitidos: list):
    def dependencia(usuario: models.Usuario = Depends(obtener_usuario_actual)):
        if not usuario:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")
        if usuario.rol.value not in roles_permitidos:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado. Permisos insuficientes.")
        return usuario
    return dependencia
