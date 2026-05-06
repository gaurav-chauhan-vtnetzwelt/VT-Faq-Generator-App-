import logging
from services.scraper import fetch_content, validate_url
from services.sitemap import parse_sitemap, extract_sitemap_context
from services.internal_links import (
    apply_inline_internal_links,
    filter_same_site,
    filter_urls_by_page_relevance,
)
from core.ai_client import generate_faqs_ai, FAQGenerationError
from core.ranking import remove_duplicates
from core.ranking_system import rank_faqs, filter_low_quality
from core.config import MAX_SOURCE_CONTENT_FOR_LLM, DEFAULT_FAQ_COUNT

logger = logging.getLogger(__name__)


def run_pipeline(
    urls: list,
    faq_count: int = DEFAULT_FAQ_COUNT,
    sitemap_url: str = None,
    *,
    keywords: str | None = None,
    country: str | None = None,
    language: str | None = None,
    page_type: str | None = None,
    industry_niche: str | None = None,
) -> list:
    """
    Complete FAQ generation pipeline.

    Raises FAQGenerationError when AI is configured but generation fails.
    """

    logger.info(f"Starting pipeline: {len(urls)} URLs, {faq_count} FAQs requested")

    blocks = []
    for url in urls:
        logger.info(f"Fetching content from {url}")
        if validate_url(url):
            content = fetch_content(url)
            if content:
                blocks.append(f"--- SOURCE PAGE ({url}) ---\n{content}")
        else:
            logger.warning(f"URL validation failed: {url}")

    if not blocks:
        logger.error("No valid content fetched")
        return []

    merged_content = "\n\n".join(blocks)[:MAX_SOURCE_CONTENT_FOR_LLM]
    logger.info(f"Labeled merged content size: {len(merged_content)} characters")

    internal_urls: list[str] = []
    sitemap_context = ""
    if sitemap_url:
        logger.info(f"Parsing sitemap: {sitemap_url}")
        raw_sm = parse_sitemap(sitemap_url)
        internal_urls = filter_same_site(urls, raw_sm)
        if not internal_urls and raw_sm:
            internal_urls = list(dict.fromkeys(raw_sm))[:60]

        internal_urls = filter_urls_by_page_relevance(
            urls,
            internal_urls,
            merged_content,
            max_urls=28,
        )
        logger.info(
            "Scoped internal link candidates to %s URLs relevant to the source page(s)",
            len(internal_urls),
        )

        sitemap_context = extract_sitemap_context(internal_urls)

    logger.info("Generating FAQs with AI...")
    raw_faqs = generate_faqs_ai(
        merged_content,
        min(faq_count * 2, 50),
        sitemap_context,
        keywords=keywords,
        country=country,
        language=language,
        page_type=page_type,
        industry_niche=industry_niche,
        internal_links=internal_urls if internal_urls else None,
        source_page_urls=urls,
    )

    if not raw_faqs:
        logger.error("AI generation returned no FAQs")
        raise FAQGenerationError(
            "The AI returned no FAQs. Check your API key and try again."
        )

    logger.info(f"Generated {len(raw_faqs)} raw FAQs")

    logger.info("Removing duplicates...")
    unique_faqs = remove_duplicates(raw_faqs)
    logger.info(f"After deduplication: {len(unique_faqs)} FAQs")

    logger.info("Ranking by quality...")
    ranked_faqs = rank_faqs(unique_faqs)

    logger.info("Filtering low-quality FAQs...")
    filtered_faqs = filter_low_quality(ranked_faqs, min_score=1.0)

    final_faqs = filtered_faqs[:faq_count]

    if internal_urls or urls:
        inject_pool = list(dict.fromkeys([u for u in urls if u] + internal_urls))
        apply_inline_internal_links(
            final_faqs,
            inject_pool,
            keywords_csv=keywords,
        )

    logger.info(f"Pipeline complete: {len(final_faqs)} FAQs returned")

    return final_faqs


def validate_faq_list(faqs: list) -> bool:
    if not isinstance(faqs, list):
        return False

    for faq in faqs:
        if not isinstance(faq, dict):
            return False
        if "question" not in faq or "answer" not in faq:
            return False

    return True
