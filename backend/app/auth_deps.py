from typing import Annotated, Optional
import uuid

import jwt
from fastapi import Depends, Header, HTTPException

from app.config import get_settings


def _decode_supabase_user(authorization: Optional[str]) -> uuid.UUID:
    s = get_settings()
    secret = s.supabase_jwt_secret
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if secret:
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={"verify_aud": False},
            )
            sub = payload.get("sub")
            if not sub:
                raise HTTPException(status_code=401, detail="Invalid token")
            return uuid.UUID(sub)
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e
    # Dev fallback: treat raw token as UUID user id (local only)
    try:
        return uuid.UUID(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail="Invalid dev token (expected UUID)") from e


async def current_user_id(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_dev_user_id: Optional[str] = Header(None, alias="X-Dev-User-Id"),
) -> uuid.UUID:
    s = get_settings()
    secret = s.supabase_jwt_secret
    if authorization:
        return _decode_supabase_user(authorization)
    if not secret and x_dev_user_id:
        try:
            return uuid.UUID(x_dev_user_id)
        except ValueError as e:
            raise HTTPException(status_code=401, detail="Bad X-Dev-User-Id") from e
    raise HTTPException(status_code=401, detail="Unauthorized")


CurrentUserId = Annotated[uuid.UUID, Depends(current_user_id)]
