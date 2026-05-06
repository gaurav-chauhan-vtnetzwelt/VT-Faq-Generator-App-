import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
import logging

logger = logging.getLogger(__name__)

def compute_text_embeddings(texts: list) -> np.ndarray:
    """
    Compute embeddings for a list of texts using TF-IDF.
    This is a lightweight alternative to expensive embedding APIs.
    """
    if not texts:
        return np.array([])
    
    try:
        vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
        embeddings = vectorizer.fit_transform(texts).toarray()
        return embeddings
    except Exception as e:
        logger.error(f"Error computing embeddings: {e}")
        return np.array([])

def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity between two texts (0-1 scale).
    """
    try:
        embeddings = compute_text_embeddings([text1, text2])
        if len(embeddings) < 2:
            return 0.0
        similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
        return float(similarity)
    except Exception as e:
        logger.error(f"Error calculating similarity: {e}")
        return 0.0

def remove_duplicates(faqs: list, threshold: float = 0.85) -> list:
    """
    Remove duplicate or very similar FAQs using cosine similarity.
    """
    if not faqs:
        return []
    
    try:
        questions = [f["question"] for f in faqs]
        embeddings = compute_text_embeddings(questions)
        
        if embeddings.size == 0:
            return faqs
        
        unique_indices = []
        for i, vec in enumerate(embeddings):
            is_unique = True
            for j in unique_indices:
                similarity = cosine_similarity([vec], [embeddings[j]])[0][0]
                if similarity > threshold:
                    is_unique = False
                    break
            if is_unique:
                unique_indices.append(i)
        
        unique_faqs = [faqs[i] for i in unique_indices]
        logger.info(f"Removed {len(faqs) - len(unique_faqs)} duplicate FAQs")
        return unique_faqs
    
    except Exception as e:
        logger.error(f"Error removing duplicates: {e}")
        return faqs
