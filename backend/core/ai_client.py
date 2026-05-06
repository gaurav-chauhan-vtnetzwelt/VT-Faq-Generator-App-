import json
import logging
import random

import requests
from openai import OpenAI

from core.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
    OPENAI_API_KEY,
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
    return selected


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


def _groq_chat(prompt: str, max_tokens: int, temperature: float) -> str:
    client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=0.9,
    )
    return response.choices[0].message.content.strip()


def _openai_chat(prompt: str, max_tokens: int, temperature: float) -> str:
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
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


def call_llm(prompt: str, max_tokens: int = 2000, temperature: float = 0.7) -> str:
    provider = active_ai_provider()
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


def generate_faqs_ai(content: str, faq_count: int, sitemap_context: str = "") -> list:
    """
    Generate FAQs via Groq (free tier), Gemini (free tier), or OpenAI.
    Falls back to canned demo FAQs when no provider is configured.
    """
    if not has_real_ai_credentials() or active_ai_provider() == "demo":
        logger.info("Using DEMO MODE — Generating %s sample FAQs", faq_count)
        return _get_demo_faqs(content, faq_count)

    prompt = f"""You are an SEO expert FAQ specialist.

Generate exactly {faq_count} high-quality, unique FAQs from the provided content.

CRITICAL RULES:
- Each question must be 8-15 words
- Avoid generic/duplicate questions
- Answers must be 40-80 words
- Use natural language (conversational)
- Include relevant keywords naturally
- Make answers actionable and specific
- Number FAQs clearly

Content to analyze:
{content[:3000]}

{f"Related pages from sitemap: {sitemap_context}" if sitemap_context else ""}

Return ONLY a valid JSON array with no markdown formatting:
[
  {{"question": "Your question here?", "answer": "Your answer here."}},
  {{"question": "Another question?", "answer": "Answer text here."}}
]

Make sure the JSON is valid and parseable."""

    response_text = ""
    try:
        response_text = call_llm(prompt, max_tokens=2000, temperature=0.7)
        response_text = _strip_json_fence(response_text)
        faqs = json.loads(response_text)
        if not isinstance(faqs, list):
            logger.warning("Response was not a list, wrapping it")
            faqs = [faqs]
        return faqs[:faq_count]
    except json.JSONDecodeError as e:
        snippet = (response_text[:400] + "…") if len(response_text) > 400 else response_text
        logger.error("Failed to parse AI JSON: %s. Snippet: %s", e, snippet)
        raise FAQGenerationError(
            "The model did not return valid JSON. Try again or lower the FAQ count. "
            f"Parse error: {e}"
        ) from e
    except FAQGenerationError:
        raise
    except Exception as e:
        logger.error("Error generating FAQs: %s", e, exc_info=True)
        raise FAQGenerationError(str(e)) from e


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
