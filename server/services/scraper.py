import requests
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

def fetch_content(url: str, timeout: int = 10) -> str:
    """
    Fetch and extract text content from a URL.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "meta", "link"]):
            script.decompose()
        
        # Get text
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        logger.info(f"Scraped {len(text)} characters from {url}")
        return text
    
    except requests.RequestException as e:
        logger.error(f"Error fetching {url}: {e}")
        return ""
    except Exception as e:
        logger.error(f"Unexpected error scraping {url}: {e}")
        return ""

def validate_url(url: str) -> bool:
    """
    Validate if a URL is accessible.
    """
    try:
        response = requests.head(url, timeout=5, allow_redirects=True)
        return response.status_code < 400
    except Exception as e:
        logger.warning(f"URL validation failed for {url}: {e}")
        return False
