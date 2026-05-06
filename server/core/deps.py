from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from core.auth_token import decode_access_token
from services.users import get_user_by_id

security = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: str
    username: str
    role: str


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
        uid = payload.get("sub")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token")
        doc = get_user_by_id(uid)
        if not doc or doc.get("disabled"):
            raise HTTPException(status_code=401, detail="User inactive or deleted")
        role = doc.get("role") or "user"
        uname = doc.get("username") or payload.get("username") or ""
        return CurrentUser(id=uid, username=uname, role=role)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None


async def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user
