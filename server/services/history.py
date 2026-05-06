from datetime import datetime

from bson import ObjectId

from db.mongo import history
import logging

logger = logging.getLogger(__name__)


def save_history(data: dict, *, user_id: str | None = None) -> str | None:
    try:
        record = {
            **data,
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "status": "completed",
        }
        result = history.insert_one(record)
        logger.info("Saved history record: %s", result.inserted_id)
        return str(result.inserted_id)
    except Exception as e:
        logger.error("Error saving history: %s", e)
        return None


def get_history(
    project_id: str | None = None,
    limit: int = 50,
    *,
    user_id: str | None = None,
    is_admin: bool = False,
):
    try:
        q: dict = {}
        if project_id:
            q["project_id"] = project_id
        if not is_admin:
            q["user_id"] = user_id
        records = list(history.find(q).sort("created_at", -1).limit(limit))

        out = []
        for record in records:
            r = dict(record)
            r["_id"] = str(record["_id"])
            out.append(r)
        return out
    except Exception as e:
        logger.error("Error retrieving history: %s", e)
        return []


def delete_history(history_id: str) -> bool:
    try:
        result = history.delete_one({"_id": ObjectId(history_id)})
        return result.deleted_count > 0
    except Exception as e:
        logger.error("Error deleting history: %s", e)
        return False
