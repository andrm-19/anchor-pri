import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY

PASSWORD_POLICY_HINT = (
    "La contrasena debe tener minimo 8 caracteres, una mayuscula, "
    "una minuscula y un numero."
)

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def validate_password_strength(password: str) -> List[str]:
    issues: List[str] = []

    if len(password) < 8:
        issues.append("Debe tener al menos 8 caracteres.")
    if not re.search(r"[A-Z]", password):
        issues.append("Debe incluir una letra mayuscula.")
    if not re.search(r"[a-z]", password):
        issues.append("Debe incluir una letra minuscula.")
    if not re.search(r"\d", password):
        issues.append("Debe incluir un numero.")
    if re.search(r"\s", password):
        issues.append("No debe contener espacios.")

    return issues


def is_strong_password(password: str) -> bool:
    return not validate_password_strength(password)


def create_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado.",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido.",
        ) from exc


def get_token_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Debes iniciar sesion para acceder a este recurso.",
        )

    return decode_token(credentials.credentials)


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    payload = get_token_payload(credentials)
    username = payload.get("sub")

    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin usuario valido.",
        )

    return username
