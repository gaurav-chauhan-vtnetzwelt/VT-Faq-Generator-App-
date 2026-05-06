import copy
import json
import logging
import random

import requests
from openai import APIStatusError, OpenAI, RateLimitError

from core.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
    MAX_SOURCE_CONTENT_FOR_LLM,
    MOCK_AI,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    AI_PROVIDER,
    has_real_ai_credentials,
)

logger = logging.getLogger(__name__)


class FAQGenerationError(RuntimeError):
    """AI generation failed; do not substitute canned demo FAQs."""

# --- Demo content (no API key) ---

DEMO_FAQS = {
    "technology": [
        {"question": "What is cloud computing?", "answer": "Cloud computing is the delivery of computing services over the internet, including servers, storage, and applications. It allows businesses to access resources on-demand without managing physical infrastructure, reducing costs and improving scalability."},
        {"question": "How does machine learning work?", "answer": "Machine learning uses algorithms to learn patterns from data and make predictions. Systems improve through training on examples, automatically adjusting parameters to minimize errors. It powers applications like recommendation systems, image recognition, and natural language processing."},
        {"question": "What is cybersecurity?", "answer": "Cybersecurity involves protecting digital systems, networks, and data from unauthorized access and attacks. It includes firewalls, encryption, authentication, and security awareness training. Strong cybersecurity is essential for protecting sensitive information and maintaining business continuity."},
        {"question": "What are APIs and why use them?", "answer": "APIs (Application Programming Interfaces) allow different software systems to communicate and share data. They enable developers to build applications quickly by leveraging existing functionality. APIs are crucial for integrations, third-party services, and creating robust ecosystems."},
        {"question": "What is the difference between frontend and backend?", "answer": "Frontend is the user-facing part of applications that users interact with, built with HTML, CSS, and JavaScript. Backend handles server-side logic, databases, and business operations. They work together to create complete web applications."},
    ],
    "business": [
        {"question": "What is digital marketing?", "answer": "Digital marketing uses online channels like social media, email, and search engines to reach customers. It includes content marketing, SEO, paid advertising, and analytics. Digital marketing allows businesses to target specific audiences and measure campaign effectiveness in real-time."},
        {"question": "What is customer retention?", "answer": "Customer retention is keeping existing customers engaged and loyal to your brand. It's typically cheaper than acquiring new customers and leads to higher lifetime value. Strategies include excellent customer service, loyalty programs, and personalized communication."},
        {"question": "What is ROI in marketing?", "answer": "ROI (Return on Investment) measures the profit generated from marketing efforts. It's calculated as (gain - cost) / cost × 100. High ROI indicates effective marketing campaigns and helps businesses allocate budgets to successful strategies."},
        {"question": "What is a business model?", "answer": "A business model describes how a company creates, delivers, and captures value. It outlines revenue streams, customer segments, and key resources. Common models include subscription, freemium, marketplace, and licensing approaches."},
        {"question": "What is brand positioning?", "answer": "Brand positioning defines how your company wants to be perceived in the customer's mind. It differentiates your brand from competitors and communicates unique value. Effective positioning requires clarity on target audience, unique benefits, and compelling messaging."},
    ],
    "default": [
        {"question": "What information does this website provide?", "answer": "This website offers valuable resources and information to help users understand key concepts and best practices. The content is designed to be accessible, accurate, and regularly updated. Users can explore different sections to find relevant information."},
        {"question": "How can I find information quickly on this site?", "answer": "Use the search function to look for specific topics. Browse the navigation menu for different categories. Check the FAQ section for common questions. Most pages include relevant links to related content."},
        {"question": "Is this information current and reliable?", "answer": "Yes, all information is regularly reviewed and updated to ensure accuracy. Content is sourced from reputable sources and verified by experts. We maintain high editorial standards for quality and reliability."},
        {"question": "How often is the content updated?", "answer": "We update content regularly to reflect the latest information and best practices. Major updates are announced to keep users informed. Feedback from users helps us identify areas that need revision or improvement."},
        {"question": "Can I share this content?", "answer": "Yes, content can be shared within fair use guidelines. Always attribute the source and provide proper credits. For commercial use or republishing, contact us for permission."},
    ],
}


def _detect_category(content: str) -> str:
    content_lower = content.lower()
    if any(word in content_lower for word in ["api", "code", "database", "software", "algorithm", "python", "javascript", "cloud"]):
        return "technology"
    if any(word in content_lower for word in ["marketing", "business", "sales", "customer", "roi", "brand", "revenue"]):
        return "business"
    return "default"


def _get_demo_faqs(content: str, faq_count: int) -> list:
    category = _detect_category(content)
    demo_list = DEMO_FAQS.get(category, DEMO_FAQS["default"])
    selected = random.sample(demo_list, min(faq_count, len(demo_list)))
    return [copy.deepcopy(item) for item in selected]


def active_ai_provider() -> str:
    """
    Which backend to use: groq, gemini, openai, or demo.
    Priority: explicit AI_PROVIDER if key present, else Groq → Gemini → OpenAI.
    """
    explicit = AI_PROVIDER
    if explicit == "groq" and GROQ_API_KEY:
        return "groq"
    if explicit == "gemini" and GEMINI_API_KEY:
        return "gemini"
    if explicit == "openai" and OPENAI_API_KEY and not OPENAI_API_KEY.startswith("sk-test"):
        return "openai"
    if explicit in ("groq", "gemini", "openai"):
        logger.warning(
            "AI_PROVIDER=%s but matching key missing or invalid; using automatic selection",
            explicit,
        )
    if GROQ_API_KEY:
        return "groq"
    if GEMINI_API_KEY:
        return "gemini"
    if OPENAI_API_KEY and not OPENAI_API_KEY.startswith("sk-test"):
        return "openai"
    return "demo"


def _groq_models_sequence() -> list[str]:
    """Primary model first, then fallbacks (separate Groq pools / lower TPD use on small models)."""
    candidates = [
        GROQ_MODEL,
        "llama-3.1-8b-instant",
        "llama-3.1-70b-versatile",
        "mixtral-8x7b-32768",
    ]
    seen: set[str] = set()
    out: list[str] = []
    for m in candidates:
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def _groq_chat(prompt: str, max_tokens: int, temperature: float) -> str:
    client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
    last_exc: Exception | None = None
    for model_name in _groq_models_sequence():
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.9,
            )
            return response.choices[0].message.content.strip()
        except RateLimitError as e:
            logger.warning(
                "Groq rate limit on model %s — trying another Groq model if available",
                model_name,
            )
            last_exc = e
            continue
        except APIStatusError as e:
            code = getattr(e, "status_code", None)
            if code in (400, 404):
                logger.warning(
                    "Groq model %s rejected (%s) — trying next model",
                    model_name,
                    code,
                )
                last_exc = e
                continue
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError("Groq: no models to try")


def _openai_compat_base_url() -> str | None:
    """Normalize base URL for the OpenAI Python SDK (expects .../v1)."""
    if not OPENAI_BASE_URL:
        return None
    u = OPENAI_BASE_URL.strip().rstrip("/")
    if not u.endswith("/v1"):
        u = u + "/v1"
    return u


def _openai_chat(prompt: str, max_tokens: int, temperature: float) -> str:
    kwargs: dict = {"api_key": OPENAI_API_KEY}
    bu = _openai_compat_base_url()
    if bu:
        kwargs["base_url"] = bu
        logger.debug("OpenAI-compatible chat via %s model=%s", bu, OPENAI_MODEL)
    client = OpenAI(**kwargs)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=0.9,
    )
    return response.choices[0].message.content.strip()


def _gemini_chat(prompt: str, max_tokens: int, temperature: float) -> str:
    """Call Gemini REST API; retry with fallback model IDs if one returns 404 or empty output."""
    # Short names like "gemini-1.5-flash" often 404 on v1beta; prefer versioned IDs.
    preferred_order = [
        GEMINI_MODEL,
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
    ]
    models_to_try = []
    for m in preferred_order:
        if m not in models_to_try:
            models_to_try.append(m)
    tried = []
    last_empty: str | None = None

    for model in models_to_try:
        tried.append(model)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "topP": 0.9,
            },
        }
        response = requests.post(
            url,
            params={"key": GEMINI_API_KEY},
            json=payload,
            timeout=180,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 429:
            logger.error(
                "Gemini rate limited (429): %s",
                response.text[:800],
            )
            raise RuntimeError(
                "Gemini quota or rate limit exceeded (HTTP 429). Wait and retry, "
                "or enable billing / check quotas: https://ai.google.dev/gemini-api/docs/rate-limits"
            )

        if response.status_code == 404:
            logger.warning(
                "Gemini model %r not available (%s); trying fallback model",
                model,
                response.text[:200],
            )
            continue

        try:
            response.raise_for_status()
        except requests.HTTPError:
            logger.error(
                "Gemini HTTP error %s: %s",
                response.status_code,
                response.text[:1200],
            )
            raise RuntimeError(
                f"Gemini API HTTP {response.status_code}: {response.text[:500]}"
            ) from None

        data = response.json()
        if "error" in data:
            msg = data["error"].get("message", str(data["error"]))
            raise RuntimeError(f"Gemini API error: {msg}")

        pf = data.get("promptFeedback") or {}
        block = pf.get("blockReason")
        if block:
            raise RuntimeError(f"Gemini blocked the request (prompt): {block}")

        candidates = data.get("candidates") or []
        if not candidates:
            last_empty = (
                "Gemini returned no candidates. "
                + (f"Response keys: {list(data.keys())}" if data else "")
            )
            logger.warning("%s — trying next model if any", last_empty)
            continue

        first = candidates[0]
        reason = first.get("finishReason")
        if reason and reason not in ("STOP", "MAX_TOKENS"):
            logger.warning("Gemini finishReason=%s — output may be incomplete", reason)

        parts = first.get("content", {}).get("parts") or []
        texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
        text = "".join(texts).strip()
        if text:
            return text

        logger.warning(
            "Gemini returned empty text for model %r (finishReason=%s); trying fallback",
            model,
            reason,
        )
        last_empty = "empty model output"

    raise RuntimeError(
        "Gemini failed for models "
        + str(tried)
        + (f". Detail: {last_empty}" if last_empty else "")
    )


def call_llm(
    prompt: str,
    max_tokens: int = 2000,
    temperature: float = 0.7,
    *,
    force_provider: str | None = None,
) -> str:
    """force_provider: 'groq' | 'gemini' | 'openai' — bypass auto selection (for 429 fallback)."""
    provider = force_provider or active_ai_provider()
    if provider == "demo":
        raise RuntimeError("call_llm should not run in demo mode")
    if provider == "groq":
        return _groq_chat(prompt, max_tokens, temperature)
    if provider == "gemini":
        return _gemini_chat(prompt, max_tokens, temperature)
    return _openai_chat(prompt, max_tokens, temperature)


def _strip_json_fence(text: str) -> str:
    response_text = text.strip()
    if response_text.startswith("```"):
        parts = response_text.split("```")
        if len(parts) >= 2:
            response_text = parts[1]
            if response_text.lstrip().startswith("json"):
                response_text = response_text.lstrip()[4:]
    return response_text.strip()


def _rate_limited(err: str) -> bool:
    e = err.lower()
    return "429" in err or "resource_exhausted" in e or "quota" in e or "rate limit" in e


def _friendly_rate_limit_message(original: Exception) -> str:
    """Short message for UI when Groq/Gemini hit quota (avoid dumping raw JSON)."""
    if isinstance(original, RateLimitError):
        return (
            "AI provider rate limit reached (daily quota or too many requests). "
            "Wait and retry, choose another provider in server/.env (e.g. set GEMINI_API_KEY "
            "or OPENAI_API_KEY), or upgrade your Groq plan."
        )
    return str(original)


def generate_faqs_ai(
    content: str,
    faq_count: int,
    sitemap_context: str = "",
    *,
    keywords: str | None = None,
    country: str | None = None,
    language: str | None = None,
    page_type: str | None = None,
    industry_niche: str | None = None,
    internal_links: list[str] | None = None,
    source_page_urls: list[str] | None = None,
) -> list:
    """
    Generate FAQs via Groq (free tier), Gemini (free tier), or OpenAI.
    Falls back to canned demo FAQs when no provider is configured.
    If MOCK_AI=1: no API calls (sample FAQs for local testing).
    If Gemini hits 429 and GROQ_API_KEY is set: one retry via Groq.
    """
    context_lines = []
    if industry_niche and str(industry_niche).strip():
        context_lines.append(f"Industry / niche: {str(industry_niche).strip()}")
    if keywords and str(keywords).strip():
        context_lines.append(f"Target keywords / themes: {str(keywords).strip()}")
    if country and str(country).strip():
        context_lines.append(f"Target country / region: {str(country).strip()}")
    if language and str(language).strip():
        context_lines.append(f"Language for all answers: {str(language).strip()}")
    if page_type and str(page_type).strip():
        context_lines.append(f"Page / site type: {str(page_type).strip()}")
    audience_block = "\n".join(context_lines)

    demo_seed = content
    if audience_block:
        demo_seed = audience_block + "\n\n" + content

    if MOCK_AI:
        logger.warning("MOCK_AI enabled — returning sample FAQs (set MOCK_AI=0 for real AI)")
        return _get_demo_faqs(demo_seed, faq_count)

    if not has_real_ai_credentials() or active_ai_provider() == "demo":
        logger.info("Using DEMO MODE — Generating %s sample FAQs", faq_count)
        return _get_demo_faqs(demo_seed, faq_count)

    src_urls = source_page_urls or []
    sources_hdr = ""
    if src_urls:
        sources_hdr = "Pages you must stay faithful to:\n" + "\n".join(f"- {u}" for u in src_urls)

    links_hdr = ""
    link_rules = ""
    if internal_links:
        numbered = "\n".join(f"{i}. {u}" for i, u in enumerate(internal_links[:45], start=1))
        links_hdr = (
            "INTERNAL SITE URLs (from sitemap — these are real pages on this site):\n"
            + numbered
        )
        link_rules = """
INTERNAL LINKS (when the INTERNAL SITE URLs list exists):
- Put links **only inside the answer sentences**: wrap words or phrases that **already appear** in your answer and that relate to the linked page — use <a href="EXACT_URL_FROM_LIST">exact same wording as in the sentence</a>.
- Do **not** add sentences like "Read more", "Click here", or paste bare URLs as visible text.
- Only link where it helps; many answers may have zero links.
"""

    grounding = """
SCOPE (critical):
- The user chose specific SOURCE PAGE(s). Every FAQ must stay within the same subject matter as that page’s content (e.g. if the page is about mobile app development, every question must be about mobile apps / that offering — not Salesforce, Magento, generic AI industry topics, real estate, or other site areas unless those words appear in SOURCE CONTENT below).

CONTENT GROUNDING:
- Base questions and answers ONLY on topics, services, claims, or facts stated or clearly implied in SOURCE CONTENT.
- Do NOT write FAQs “about” unrelated products, competitors, or verticals that are not discussed on this page (even if they exist elsewhere on the site).
- Do NOT invent statistics, guarantees, pricing, or awards not in the source.
"""

    prompt = f"""You are an SEO expert FAQ specialist.

Generate exactly {faq_count} high-quality, unique FAQs.

{grounding}

AUDIENCE AND STYLE:
{audience_block if audience_block else "(Infer tone from source content.)"}
- Align with industry/niche and keywords when provided.
- Match page type (ecommerce vs blog vs services) in tone.
- Use the requested language for Q&A when specified.

{sources_hdr}

{links_hdr}

{link_rules}

CRITICAL RULES:
- Each question: 8–15 words, specific to the source material.
- Answers: 45–90 words.
- Avoid duplicate or overlapping questions.
- Conversational, actionable, specific — not boilerplate filler.
- Escape double quotes inside JSON strings properly if the answer contains HTML attributes.

SOURCE CONTENT (labeled by page — only factual basis for topics and wording):
{content[:MAX_SOURCE_CONTENT_FOR_LLM]}

Return ONLY a valid JSON array, no markdown fences:
[
  {{"question": "Your question here?", "answer": "Your answer here."}},
  {{"question": "Another question?", "answer": "Answer text here."}}
]
"""

    temp = 0.48 if (internal_links or sitemap_context) else 0.62
    max_out = 2800

    response_text = ""

    def _parse_and_trim(text: str) -> list:
        text = _strip_json_fence(text)
        faqs = json.loads(text)
        if not isinstance(faqs, list):
            logger.warning("Response was not a list, wrapping it")
            faqs = [faqs]
        return faqs[:faq_count]

    try:
        response_text = call_llm(prompt, max_tokens=max_out, temperature=temp)
        return _parse_and_trim(response_text)
    except json.JSONDecodeError as e:
        snippet = (response_text[:400] + "…") if len(response_text) > 400 else response_text
        logger.error("Failed to parse AI JSON: %s. Snippet: %s", e, snippet)
        raise FAQGenerationError(
            "The model did not return valid JSON. Try again or lower the FAQ count. "
            f"Parse error: {e}"
        ) from e
    except Exception as e:
        err_msg = str(e)
        provider = active_ai_provider()

        if _rate_limited(err_msg) and GROQ_API_KEY and provider == "gemini":
            logger.warning("Gemini rate limited — retrying once with Groq")
            try:
                response_text = call_llm(
                    prompt, max_tokens=max_out, temperature=temp, force_provider="groq"
                )
                return _parse_and_trim(response_text)
            except json.JSONDecodeError as je:
                raise FAQGenerationError(
                    "Groq returned invalid JSON after Gemini rate limit. " + str(je)
                ) from je
            except Exception as e2:
                raise FAQGenerationError(
                    "Gemini rate limited and Groq fallback failed: " + str(e2)
                ) from e2

        # Groq exhausted (all models) or org TPD — try Gemini / OpenAI if configured
        if _rate_limited(err_msg) and provider == "groq":
            if GEMINI_API_KEY:
                logger.warning("Groq rate limited — falling back to Gemini")
                try:
                    response_text = call_llm(
                        prompt, max_tokens=max_out, temperature=temp, force_provider="gemini"
                    )
                    return _parse_and_trim(response_text)
                except json.JSONDecodeError as je:
                    raise FAQGenerationError(
                        "Gemini returned invalid JSON after Groq rate limit. " + str(je)
                    ) from je
                except Exception as e2:
                    err2 = str(e2)
                    if (
                        OPENAI_API_KEY
                        and not OPENAI_API_KEY.startswith("sk-test")
                        and _rate_limited(err2)
                    ):
                        logger.warning("Gemini also rate limited — falling back to OpenAI")
                        try:
                            response_text = call_llm(
                                prompt,
                                max_tokens=max_out,
                                temperature=temp,
                                force_provider="openai",
                            )
                            return _parse_and_trim(response_text)
                        except json.JSONDecodeError as je:
                            raise FAQGenerationError(
                                "OpenAI returned invalid JSON. " + str(je)
                            ) from je
                        except Exception as e3:
                            raise FAQGenerationError(
                                _friendly_rate_limit_message(e3)
                            ) from e3
                    raise FAQGenerationError(
                        "Groq quota exceeded and Gemini fallback failed: " + err2
                    ) from e2
            if OPENAI_API_KEY and not OPENAI_API_KEY.startswith("sk-test"):
                logger.warning("Groq rate limited — falling back to OpenAI")
                try:
                    response_text = call_llm(
                        prompt, max_tokens=max_out, temperature=temp, force_provider="openai"
                    )
                    return _parse_and_trim(response_text)
                except json.JSONDecodeError as je:
                    raise FAQGenerationError(
                        "OpenAI returned invalid JSON. " + str(je)
                    ) from je
                except Exception as e2:
                    raise FAQGenerationError(_friendly_rate_limit_message(e2)) from e2
            logger.error("Error generating FAQs: %s", e, exc_info=True)
            raise FAQGenerationError(_friendly_rate_limit_message(e)) from e

        logger.error("Error generating FAQs: %s", e, exc_info=True)
        raise FAQGenerationError(err_msg) from e


def enhance_answer(question: str, answer: str) -> str:
    if not has_real_ai_credentials() or active_ai_provider() == "demo":
        return answer

    prompt = f"""Enhance this FAQ answer to be more SEO-friendly and valuable.

Question: {question}
Current Answer: {answer}

Make it:
- 40-80 words
- Include relevant keywords
- More specific and actionable
- Professional but conversational

Return only the enhanced answer, no explanations."""

    try:
        return call_llm(prompt, max_tokens=300, temperature=0.5)
    except Exception as e:
        logger.error("Error enhancing answer: %s", e)
        return answer


__all__ = [
    "FAQGenerationError",
    "active_ai_provider",
    "call_llm",
    "enhance_answer",
    "generate_faqs_ai",
]
