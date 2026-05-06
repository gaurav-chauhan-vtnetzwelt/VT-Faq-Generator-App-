import logging
import re

logger = logging.getLogger(__name__)

def score_faq(faq: dict) -> float:
    """
    Score an FAQ based on SEO and quality metrics.
    Higher score = better quality.
    """
    score = 0.0
    question = faq.get("question", "").lower()
    answer = faq.get("answer", "").lower()
    
    # Question length (8-15 words is ideal)
    q_words = len(question.split())
    if 8 <= q_words <= 15:
        score += 2
    elif q_words > 5:
        score += 1
    
    # Answer length (40-80 words is ideal)
    a_words = len(answer.split())
    if 40 <= a_words <= 80:
        score += 2
    elif a_words >= 30:
        score += 1
    
    # Question starts with common FAQ patterns
    faq_patterns = ["how", "what", "why", "when", "where", "which", "does", "can", "will", "is"]
    if any(question.startswith(p) for p in faq_patterns):
        score += 2
    
    # High-intent keywords (e.g., cost, price, benefits, features)
    high_intent_keywords = ["cost", "price", "free", "features", "benefits", "how to", 
                            "best", "difference", "alternative", "comparison", "requirements"]
    if any(keyword in question for keyword in high_intent_keywords):
        score += 1.5
    
    # No generic answers
    generic_phrases = ["it depends", "various", "multiple", "basically"]
    if not any(phrase in answer for phrase in generic_phrases):
        score += 1
    
    # Question is specific (contains keywords)
    if len(set(question.split())) > len(set(question.split())) * 0.5:
        score += 0.5
    
    # Answer has numbers/data
    if re.search(r'\d+', answer):
        score += 1
    
    return score

def rank_faqs(faqs: list) -> list:
    """
    Rank FAQs by quality score (highest first).
    """
    try:
        scored_faqs = [(faq, score_faq(faq)) for faq in faqs]
        scored_faqs.sort(key=lambda x: x[1], reverse=True)
        ranked = [faq for faq, _ in scored_faqs]
        
        logger.info(f"Ranked {len(ranked)} FAQs by quality score")
        return ranked
    
    except Exception as e:
        logger.error(f"Error ranking FAQs: {e}")
        return faqs

def filter_low_quality(faqs: list, min_score: float = 1.0) -> list:
    """
    Filter out low-quality FAQs.
    """
    try:
        filtered = [faq for faq in faqs if score_faq(faq) >= min_score]
        logger.info(f"Filtered FAQs: {len(faqs)} -> {len(filtered)}")
        return filtered
    
    except Exception as e:
        logger.error(f"Error filtering FAQs: {e}")
        return faqs
