from contextlib import asynccontextmanager
import logging
import os
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware

from core.auth_token import create_access_token
from core.config import (
    ENVIRONMENT,
    cors_allow_origins,
    has_real_ai_credentials,
    LOG_LEVEL,
)
from core.ai_client import active_ai_provider, FAQGenerationError
from core.deps import CurrentUser, get_current_user, require_admin

from models.schemas import (
    AdminUserCreate,
    ExportRequest,
    FAQRequest,
    FAQResponse,
    LoginRequest,
    ProjectCreate,
)
from services.pipeline import run_pipeline
from services.history import save_history, get_history
from services.projects import create_project, get_projects, get_project, delete_project
from services.export_faqs import answer_to_plain_export, export_faqs_bytes
from services import users as users_service
from db.mongo import history as history_col, projects as projects_col, users as users_col

# Setup logging (LOG_LEVEL env: DEBUG, INFO, WARNING, ERROR)
_lvl = getattr(logging, LOG_LEVEL, logging.INFO)
logging.basicConfig(
    level=_lvl,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DEMO_MODE = not has_real_ai_credentials()
if DEMO_MODE:
    logger.warning(
        "⭐ DEMO MODE ACTIVE — sample FAQs only. Set GROQ_API_KEY or GEMINI_API_KEY (free) "
        "or OPENAI_API_KEY for real generation."
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    users_service.seed_admin_if_empty()
    yield


app = FastAPI(
    title="FAQ SaaS V7",
    description="Production-grade FAQ generation with AI",
    version="7.0.0",
    lifespan=lifespan,
)

_origins = cors_allow_origins()
if _origins == ["*"] and (ENVIRONMENT or "").lower() == "production":
    logger.warning(
        "CORS allows all origins (*). Set CORS_ORIGINS to your front-end URL(s) for production."
    )
_creds = False if _origins == ["*"] else True
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "demo_mode": not has_real_ai_credentials(),
        "ai_provider": active_ai_provider(),
        "message": "⭐ DEMO MODE — add GROQ_API_KEY or GEMINI_API_KEY for real FAQs"
        if DEMO_MODE
        else f"🔑 AI active ({active_ai_provider()})",
    }


@app.post("/api/auth/login")
async def login(body: LoginRequest):
    u = users_service.authenticate(body.username, body.password)
    if not u:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(
        str(u["_id"]),
        u["username"],
        u.get("role") or "user",
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": users_service.user_public(u),
    }


@app.get("/api/auth/me")
async def auth_me(current: CurrentUser = Depends(get_current_user)):
    doc = users_service.get_user_by_id(current.id)
    if not doc:
        raise HTTPException(status_code=401, detail="User not found")
    return users_service.user_public(doc)


@app.get("/api/admin/stats")
async def admin_stats(_admin: CurrentUser = Depends(require_admin)):
    uc = users_col.count_documents({})
    proj_count = projects_col.count_documents({})
    hist_count = history_col.count_documents({})
    faq_total = 0
    try:
        for doc in history_col.find({}):
            faq_total += int(doc.get("result_count") or 0)
    except Exception:
        pass
    return {
        "users": uc,
        "projects": proj_count,
        "history_runs": hist_count,
        "faqs_generated_total": faq_total,
    }


@app.post("/api/admin/users")
async def admin_create_user(
    body: AdminUserCreate,
    _admin: CurrentUser = Depends(require_admin),
):
    uid, err = users_service.create_user(body.username, body.password, role=body.role)
    if err:
        raise HTTPException(status_code=400, detail=err)
    doc = users_service.get_user_by_id(uid)
    return {"id": uid, "user": users_service.user_public(doc) if doc else {}}


@app.delete("/api/admin/users/{user_id}")
async def admin_delete_user(
    user_id: str,
    current: CurrentUser = Depends(require_admin),
):
    if user_id == current.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    target = users_service.get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.get("role") == "admin":
        active_admins = sum(
            1
            for u in users_service.list_users()
            if u.get("role") == "admin" and not u.get("disabled")
        )
        if active_admins <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last admin")
    if not users_service.delete_user(user_id):
        raise HTTPException(status_code=500, detail="Delete failed")
    return {"message": "User deleted"}


@app.get("/api/admin/users")
async def admin_list_users(_admin: CurrentUser = Depends(require_admin)):
    return {"users": users_service.list_users()}


@app.post("/api/generate", response_model=FAQResponse)
async def generate_faqs(req: FAQRequest, current: CurrentUser = Depends(get_current_user)):
    try:
        logger.info("Generating FAQs for %s URLs", len(req.urls))

        faqs = run_pipeline(
            urls=req.urls,
            faq_count=req.faq_count,
            sitemap_url=req.sitemap_url,
            keywords=req.keywords,
            country=req.country,
            language=req.language,
            page_type=req.page_type,
            industry_niche=req.industry_niche,
        )

        history_id = save_history(
            {
                "urls": req.urls,
                "faq_count": req.faq_count,
                "sitemap_url": req.sitemap_url,
                "project_id": req.project_id,
                "result_count": len(faqs),
                "faqs": faqs,
                "keywords": req.keywords,
                "country": req.country,
                "language": req.language,
                "page_type": req.page_type,
                "industry_niche": req.industry_niche,
            },
            user_id=current.id,
        )

        logger.info("Generated %s FAQs (history_id: %s)", len(faqs), history_id)

        return FAQResponse(
            faqs=faqs,
            count=len(faqs),
            status="success",
            history_id=history_id,
        )

    except FAQGenerationError as e:
        logger.error("FAQ generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        logger.error("Error in generate endpoint: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/projects")
async def list_projects(current: CurrentUser = Depends(get_current_user)):
    try:
        is_ad = current.role == "admin"
        plist = get_projects(user_id=current.id, is_admin=is_ad)
        return {"projects": plist}
    except Exception as e:
        logger.error("Error listing projects: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/projects")
async def create_new_project(req: ProjectCreate, current: CurrentUser = Depends(get_current_user)):
    try:
        project_id = create_project(
            name=req.name,
            description=req.description or "",
            urls=req.urls or [],
            user_id=current.id,
        )
        return {"id": project_id, "message": "Project created successfully"}
    except Exception as e:
        logger.error("Error creating project: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}")
async def get_project_details(project_id: str, current: CurrentUser = Depends(get_current_user)):
    try:
        is_ad = current.role == "admin"
        project = get_project(project_id, user_id=current.id, is_admin=is_ad)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return project
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting project: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/projects/{project_id}")
async def delete_project_endpoint(project_id: str, current: CurrentUser = Depends(get_current_user)):
    try:
        is_ad = current.role == "admin"
        success = delete_project(project_id, user_id=current.id, is_admin=is_ad)
        if not success:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"message": "Project deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting project: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/export")
async def export_faqs_file(req: ExportRequest, current: CurrentUser = Depends(get_current_user)):
    try:
        faqs_dump = [f.model_dump() for f in req.faqs]
        body, filename, mime = export_faqs_bytes(
            req.format, faqs_dump, title=req.title or "FAQs"
        )
        return Response(
            content=body,
            media_type=mime.split(";")[0].strip(),
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Export failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history")
async def get_history_list(
    project_id: str | None = None,
    limit: int = 50,
    current: CurrentUser = Depends(get_current_user),
):
    try:
        is_ad = current.role == "admin"
        records = get_history(
            project_id=project_id,
            limit=limit,
            user_id=current.id,
            is_admin=is_ad,
        )
        return {"history": records}
    except Exception as e:
        logger.error("Error getting history: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/schema")
async def generate_schema(faqs: list, current: CurrentUser = Depends(get_current_user)):
    try:
        schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": f.get("question") or "",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": answer_to_plain_export(f.get("answer") or ""),
                    },
                }
                for f in faqs
            ],
        }
        return schema
    except Exception as e:
        logger.error("Error generating schema: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_static_candidates = [
    os.path.join(_repo_root, "web"),
    os.path.join(_repo_root, "react-app", "build"),
]
_static_dir = next((p for p in _static_candidates if os.path.exists(p)), None)

if _static_dir:
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
else:

    @app.get("/")
    async def root():
        return {
            "message": "FAQ SaaS V7 - API is ready",
            "docs": "/docs",
            "api": "Use /api/* endpoints",
            "health": "/api/health",
        }


logger.info("FAQ SaaS V7 application started successfully")
