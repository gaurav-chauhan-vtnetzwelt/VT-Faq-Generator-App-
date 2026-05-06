import re

from pydantic import BaseModel, Field, field_validator
from typing import List, Literal, Optional

PAGE_TYPES = ("services", "blog", "ecommerce", "category", "landing", "support", "other")


def normalize_keywords_field(v: Optional[str]) -> Optional[str]:
    """Split on comma, semicolon, newline; trim; rejoin as comma-separated."""
    if v is None or not str(v).strip():
        return None
    parts = re.split(r"[,;\n]+", str(v))
    cleaned = [p.strip() for p in parts if p.strip()]
    return ", ".join(cleaned) if cleaned else None


class FAQRequest(BaseModel):
    """Request schema for FAQ generation."""
    urls: List[str] = Field(..., min_length=1, max_length=10)
    faq_count: int = Field(default=5, ge=1, le=50)
    sitemap_url: Optional[str] = None
    project_id: Optional[str] = None
    # AI / audience context
    keywords: Optional[str] = Field(
        default=None,
        description="Comma/semicolon-separated keywords to steer FAQ topics",
    )
    country: Optional[str] = Field(default=None, max_length=120)
    language: Optional[str] = Field(default=None, max_length=80)
    page_type: Optional[str] = Field(default=None, max_length=40)
    industry_niche: Optional[str] = Field(default=None, max_length=300)

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, v):
        if not v:
            raise ValueError("At least one URL is required")
        return v

    @field_validator("keywords")
    @classmethod
    def normalize_keywords(cls, v):
        return normalize_keywords_field(v)

    @field_validator("page_type")
    @classmethod
    def normalize_page_type(cls, v):
        if v is None or v == "":
            return None
        low = v.strip().lower()
        if low not in PAGE_TYPES:
            return low[:40]
        return low

class FAQItem(BaseModel):
    """Single FAQ item."""
    question: str = Field(..., min_length=5, max_length=200)
    answer: str = Field(..., min_length=10, max_length=25000)

class FAQResponse(BaseModel):
    """Response schema for FAQ generation."""
    faqs: List[FAQItem]
    count: int
    status: str = "success"
    history_id: Optional[str] = None


class ExportRequest(BaseModel):
    """Export generated FAQs to a file format."""

    format: Literal["docx", "xlsx", "pdf", "csv"]
    faqs: List[FAQItem]
    title: Optional[str] = Field(default="FAQs", max_length=200)

class ProjectCreate(BaseModel):
    """Request schema for project creation."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    urls: Optional[List[str]] = []

class ProjectResponse(BaseModel):
    """Response schema for project."""
    id: str
    name: str
    description: Optional[str]
    created_at: str
    status: str


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., min_length=1, max_length=500)


class AdminUserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., min_length=6, max_length=500)
    role: Literal["admin", "user"] = "user"
