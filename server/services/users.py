"""Users collection: auth, CRUD, admin seed."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from passlib.context import CryptContext
from pymongo.errors import DuplicateKeyError

from core.config import SEED_ADMIN_PASSWORD, SEED_ADMIN_USERNAME
from db.mongo import users as users_col

logger = logging.getLogger(__name__)

# pbkdf2_sha256 avoids bcrypt/passlib backend issues across bcrypt versions (Docker/Linux friendly).
_pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(raw: str) -> str:
    return _pwd.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return _pwd.verify(raw, hashed)
    except Exception:
        return False


def _iso(dt) -> str | None:
    if dt is None:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


def get_user_by_id(uid: str) -> dict[str, Any] | None:
    try:
        u = users_col.find_one({"_id": ObjectId(uid)})
    except InvalidId:
        return None
    return u


def get_user_by_username(username: str) -> dict[str, Any] | None:
    return users_col.find_one({"username": username.strip().lower()})


def authenticate(username: str, password: str) -> dict[str, Any] | None:
    doc = users_col.find_one({"username": username.strip().lower()})
    if not doc or doc.get("disabled"):
        return None
    if not verify_password(password, doc.get("password_hash") or ""):
        return None
    return doc


def create_user(username: str, password: str, role: str = "user") -> tuple[str | None, str | None]:
    username = username.strip().lower()
    if not username or len(username) > 120:
        return None, "Invalid username"
    if role not in ("admin", "user"):
        role = "user"
    if users_col.find_one({"username": username}):
        return None, "Username already exists"
    try:
        doc = {
            "username": username,
            "password_hash": hash_password(password),
            "role": role,
            "created_at": datetime.utcnow(),
            "disabled": False,
        }
        res = users_col.insert_one(doc)
        logger.info("Created user %s role=%s", username, role)
        return str(res.inserted_id), None
    except DuplicateKeyError:
        return None, "Username already exists"
    except Exception as e:
        if "duplicate" in str(e).lower() or "E11000" in str(e):
            return None, "Username already exists"
        logger.error("create_user failed: %s", e)
        return None, str(e)


def delete_user(uid: str) -> bool:
    try:
        oid = ObjectId(uid)
    except InvalidId:
        return False
    r = users_col.delete_one({"_id": oid})
    return r.deleted_count > 0


def seed_admin_if_empty() -> None:
    """Create default admin when there are no users (first deploy / empty DB)."""
    try:
        n = users_col.count_documents({})
    except Exception as e:
        logger.warning("Could not count users: %s", e)
        return
    if n > 0:
        return
    uid, err = create_user(SEED_ADMIN_USERNAME, SEED_ADMIN_PASSWORD, role="admin")
    if err:
        logger.error("Failed to seed admin user: %s", err)
        return
    logger.warning(
        "Seeded admin user %r (change password or set SEED_ADMIN_* / JWT_SECRET in production)",
        SEED_ADMIN_USERNAME,
    )


def user_public(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "username": doc.get("username"),
        "role": doc.get("role", "user"),
        "created_at": _iso(doc.get("created_at")),
        "disabled": bool(doc.get("disabled")),
    }


def list_users(limit: int = 500) -> list[dict[str, Any]]:
    rows = list(users_col.find().sort("created_at", -1).limit(limit))
    return [user_public(r) for r in rows]
