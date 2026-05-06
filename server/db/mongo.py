from pymongo import MongoClient
from core.config import DATABASE_NAME, MONGO_URI
import logging

logger = logging.getLogger(__name__)


try:
    # Short timeout so local dev without Mongo reaches mock mode quickly (~2s vs ~5s).
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    client.admin.command("ping")
    db = client[DATABASE_NAME]

    if "projects" not in db.list_collection_names():
        db.create_collection("projects")
    if "history" not in db.list_collection_names():
        db.create_collection("history")
    if "users" not in db.list_collection_names():
        db.create_collection("users")

    projects = db["projects"]
    history = db["history"]
    users = db["users"]

    projects.create_index("created_at")
    history.create_index("created_at")
    history.create_index("project_id")
    history.create_index("user_id")
    projects.create_index("user_id")
    users.create_index("username", unique=True)

    logger.info("MongoDB connected successfully")
except Exception as e:
    logger.warning("MongoDB connection failed: %s. Running in mock mode.", e)

    class MockCollection:
        def __init__(self):
            self.data = []

        def _match(self, doc, query):
            if not query:
                return True
            for k, v in query.items():
                if k == "_id":
                    if doc.get(k) != v:
                        return False
                    continue
                if isinstance(v, dict):
                    continue
                if doc.get(k) != v:
                    return False
            return True

        def count_documents(self, query=None):
            q = query or {}
            return len([d for d in self.data if self._match(d, q)])

        def insert_one(self, doc):
            from bson import ObjectId

            doc["_id"] = ObjectId()
            self.data.append(doc)

            class Result:
                def __init__(self, oid):
                    self.inserted_id = oid

            return Result(doc["_id"])

        def find(self, query=None):
            rows = [d for d in self.data if self._match(d, query or {})]

            class Cursor:
                def __init__(self, data):
                    self.data = list(data)

                def sort(self, key, direction=-1):
                    reverse = direction == -1
                    try:
                        self.data.sort(
                            key=lambda x: x.get(key) or "",
                            reverse=reverse,
                        )
                    except Exception:
                        pass
                    return self

                def limit(self, n):
                    self.data = self.data[:n]
                    return self

                def __iter__(self):
                    return iter(self.data)

            return Cursor(rows)

        def find_one(self, query):
            for doc in self.data:
                if self._match(doc, query):
                    return doc
            return None

        def update_one(self, query, update):
            class Result:
                modified_count = 0

            if "$set" not in update:
                return Result()
            sets = update["$set"]
            out = Result()
            for doc in self.data:
                if self._match(doc, query):
                    doc.update(sets)
                    out.modified_count = 1
                    break
            return out

        def delete_one(self, query):
            class Result:
                deleted_count = 0

            out = Result()
            for i, doc in enumerate(self.data):
                if self._match(doc, query):
                    del self.data[i]
                    out.deleted_count = 1
                    break
            return out

        def delete_many(self, query):
            before = len(self.data)
            self.data = [d for d in self.data if not self._match(d, query)]

            class Result:
                deleted_count = before - len(self.data)

            return Result()

        def create_index(self, key, **kwargs):
            pass

    projects = MockCollection()
    history = MockCollection()
    users = MockCollection()
