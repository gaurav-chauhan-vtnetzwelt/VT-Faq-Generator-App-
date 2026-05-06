import logging

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def parse_sitemap(sitemap_url: str, max_urls: int = 100, _depth: int = 0) -> list:
    """
    Parse XML sitemap or sitemap index and extract page URLs (recursive for indexes).
    """
    MAX_DEPTH = 5
    if _depth > MAX_DEPTH:
        logger.warning("Sitemap recursion depth exceeded for %s", sitemap_url)
        return []

    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(sitemap_url, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        logger.error("Error fetching sitemap %s: %s", sitemap_url, e)
        return []

    try:
        soup = BeautifulSoup(response.content, "xml")
    except Exception as e:
        logger.error("Error parsing XML for %s: %s", sitemap_url, e)
        return []

    urls: list[str] = []

    # Sitemap index only — follow nested sitemaps, do not treat loc as pages here
    if soup.find("sitemap"):
        for sm in soup.find_all("sitemap"):
            if len(urls) >= max_urls:
                break
            loc = sm.find("loc")
            if loc and loc.string:
                nested = loc.string.strip()
                remaining = max_urls - len(urls)
                child_urls = parse_sitemap(nested, max_urls=remaining, _depth=_depth + 1)
                for u in child_urls:
                    if u not in urls:
                        urls.append(u)
                    if len(urls) >= max_urls:
                        break
        logger.info(
            "Collected %s URLs from sitemap index chain starting at %s",
            len(urls),
            sitemap_url,
        )
        return urls[:max_urls]

    # Standard urlset — prefer <url><loc>
    for ue in soup.find_all("url"):
        if len(urls) >= max_urls:
            break
        loc = ue.find("loc")
        if loc and loc.string:
            u = loc.string.strip()
            if u and u not in urls:
                urls.append(u)

    # Fallback: flat <loc> list (some generators omit <url> wrapper)
    if len(urls) < max_urls:
        for loc in soup.find_all("loc"):
            if len(urls) >= max_urls:
                break
            if loc.string:
                u = loc.string.strip()
                if u and u not in urls:
                    urls.append(u)

    logger.info("Collected %s URLs from urlset %s", len(urls), sitemap_url)
    return urls[:max_urls]


def extract_sitemap_context(urls: list, limit: int = 40) -> str:
    """Human-readable numbered list for the LLM prompt."""
    if not urls:
        return ""
    lines = []
    for i, url in enumerate(urls[:limit], start=1):
        lines.append(f"{i}. {url}")
    return "\n".join(lines)
