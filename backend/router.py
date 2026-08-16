import re
from functools import lru_cache

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from faq import FAQ_QUESTIONS


# Words/patterns that unambiguously mean the user is asking about store policy.
FAQ_PATTERNS = [
    r"\breturn\b",
    r"\brefund\b",
    r"\bpayment\b",
    r"\bcash on delivery\b",
    r"\bcod\b",
    r"\btrack(?:ing)?\b.*\border\b",
    r"\border\b.*\btrack(?:ing)?\b",
    r"\bhdfc\b",
    r"\bcredit card\b",
    r"\bpromo code\b",
    r"\bcoupon\b",
    r"\binternational shipping\b",
    r"\bdamaged product\b",
    r"\bdefective\b",
    r"\bcancel\b.*\border\b",
    r"\bmodify\b.*\border\b",
    r"\bsupport\b",
]

PRODUCT_PATTERNS = [
    r"\bproduct(?:s)?\b",
    r"\bshoe(?:s)?\b",
    r"\bnike\b",
    r"\bpuma\b",
    r"\badidas\b",
    r"\bcampus\b",
    r"\bskechers\b",
    r"\bred tape\b",
    r"\bbrand\b",
    r"\bprice\b",
    r"\bcost\b",
    r"\bcheap(?:est)?\b",
    r"\bexpensive\b",
    r"\bdiscount(?:s|ed)?\b",
    r"\bsale\b",
    r"\bdeal(?:s)?\b",
    r"\boffer(?:s)?\b",
    r"\brating(?:s)?\b",
    r"\btop rated\b",
    r"\bbuy\b",
    r"\bunder\b",
    r"\babove\b",
    r"\bbetween\b",
    r"\brupees\b",
    r"\brs\.?\b",
    r"₹",
]


def _matches(patterns: list[str], query: str) -> bool:
    return any(re.search(pattern, query, flags=re.IGNORECASE) for pattern in patterns)


@lru_cache(maxsize=1)
def _faq_vectorizer():
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
    matrix = vectorizer.fit_transform(FAQ_QUESTIONS)
    return vectorizer, matrix


def route_query(query: str) -> str:
    text = query.strip().lower()

    # Product intent gets priority when a query explicitly asks for an item.
    # This prevents generic words such as "find" or "best" from accidentally
    # sending a product query to the FAQ chain.
    if _matches(PRODUCT_PATTERNS, text):
        return "sql"

    if _matches(FAQ_PATTERNS, text):
        return "faq"

    vectorizer, faq_matrix = _faq_vectorizer()
    query_vector = vectorizer.transform([text])
    faq_score = float(cosine_similarity(query_vector, faq_matrix).max())

    return "faq" if faq_score >= 0.25 else "sql"


def router(query: str):
    return route_query(query)
