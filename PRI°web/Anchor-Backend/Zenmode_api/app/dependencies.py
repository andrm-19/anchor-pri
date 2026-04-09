from fastapi import Depends, HTTPException, status

from app.auth import get_token_payload
from app.database import get_user_by_id, get_user_by_username


def get_current_user(token_payload: dict = Depends(get_token_payload)) -> dict:
    user = None
    token_user_id = token_payload.get("uid")

    if token_user_id is not None:
        try:
            user = get_user_by_id(int(token_user_id))
        except (TypeError, ValueError):
            user = None

    if user is None and token_payload.get("sub"):
        user = get_user_by_username(token_payload["sub"])

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesion ya no es valida.",
        )

    return user
