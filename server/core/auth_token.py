from time import time

from jose import JWTError, jwt

from core.config import ACCESS_TOKEN_EXPIRE_MINUTES, JWT_ALGORITHM, JWT_SECRET


def create_access_token(user_id: str, username: str, role: str) -> str:
    exp = int(time()) + ACCESS_TOKEN_EXPIRE_MINUTES * 60
    return jwt.encode(
        {"sub": user_id, "username": username, "role": role, "exp": exp},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
