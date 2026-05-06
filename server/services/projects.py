from datetime import datetime

from bson import ObjectId

from db.mongo import history, projects
import logging

logger = logging.getLogger(__name__)


def create_project(
    name: str,
    description: str = "",
    urls: list | None = None,
    *,
    user_id: str | None = None,
) -> str | None:
    try:
        project = {
            "name": name,
            "description": description,
            "urls": urls or [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "faq_count": 0,
            "status": "active",
            "user_id": user_id,
        }
        result = projects.insert_one(project)
        logger.info("Created project: %s", result.inserted_id)
        return str(result.inserted_id)
    except Exception as e:
        logger.error("Error creating project: %s", e)
        return None


def _ownership_filter(user_id: str | None, is_admin: bool) -> dict | None:
    """Mongo filter: admins see all; users only their rows (and never unscoped legacy)."""
    if is_admin:
        return None
    return {"user_id": user_id}


def get_projects(limit: int = 100, *, user_id: str | None = None, is_admin: bool = False):
    try:
        q = _ownership_filter(user_id, is_admin)
        cur = projects.find(q) if q is not None else projects.find()
        records = list(cur.sort("created_at", -1).limit(limit))

        out = []
        for record in records:
            r = dict(record)
            r["_id"] = str(record["_id"])
            out.append(r)
        return out
    except Exception as e:
        logger.error("Error retrieving projects: %s", e)
        return []


def get_project(project_id: str, *, user_id: str | None = None, is_admin: bool = False):
    try:
        project = projects.find_one({"_id": ObjectId(project_id)})
        if not project:
            return None
        if not is_admin:
            ow = project.get("user_id")
            if ow is not None and ow != user_id:
                return None
            # legacy doc without user_id: only admin
            if ow is None:
                return None
        p = dict(project)
        p["_id"] = str(project["_id"])
        return p
    except Exception as e:
        logger.error("Error retrieving project: %s", e)
        return None


def update_project(project_id: str, **kwargs) -> bool:
    try:
        update_data = {**kwargs, "updated_at": datetime.utcnow()}
        result = projects.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": update_data},
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error("Error updating project: %s", e)
        return False


def delete_project(
    project_id: str,
    *,
    user_id: str | None = None,
    is_admin: bool = False,
) -> bool:
    try:
        oid = ObjectId(project_id)
        existing = projects.find_one({"_id": oid})
        if not existing:
            return False
        if not is_admin:
            ow = existing.get("user_id")
            if ow is not None and ow != user_id:
                return False
            if ow is None:
                return False
        history.delete_many({"project_id": project_id})
        result = projects.delete_one({"_id": oid})
        return result.deleted_count > 0
    except Exception as e:
        logger.error("Error deleting project: %s", e)
        return False
