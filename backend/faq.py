import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from groq import Groq
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
FAQS_PATH = BASE_DIR / "resources" / "faq_data.csv"

FAQ_QUESTIONS: list[str] = []
FAQ_ANSWERS: list[str] = []
_vectorizer = None
_matrix = None


def ingest_faq_data(path: Path = FAQS_PATH):
    global FAQ_QUESTIONS, FAQ_ANSWERS, _vectorizer, _matrix

    if not path.exists():
        raise FileNotFoundError(f"FAQ file not found: {path}")

    df = pd.read_csv(path).fillna("")
    required = {"question", "answer"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"FAQ CSV is missing columns: {sorted(missing)}")

    FAQ_QUESTIONS = df["question"].astype(str).tolist()
    FAQ_ANSWERS = df["answer"].astype(str).tolist()

    _vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        stop_words="english",
    )
    _matrix = _vectorizer.fit_transform(FAQ_QUESTIONS)


def _retrieve(query: str, k: int = 3) -> list[str]:
    if _vectorizer is None or _matrix is None:
        ingest_faq_data()

    query_vector = _vectorizer.transform([query])
    scores = cosine_similarity(query_vector, _matrix)[0]
    indices = scores.argsort()[::-1][:k]

    # Only use reasonably relevant FAQ answers.
    return [
        FAQ_ANSWERS[i]
        for i in indices
        if scores[i] >= 0.15
    ]


def _groq_client():
    key = os.getenv("GROQ_API_KEY", "").strip()
    return Groq(api_key=key) if key else None


def generate_answer(query: str, context: list[str]) -> str:
    if not context:
        return "I don't know based on the available store information."

    client = _groq_client()
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    if client is None:
        # The application still works without an LLM key.
        return context[0]

    prompt = f"""
You are ShopAI, an e-commerce customer-support assistant.

Answer the question using ONLY the FAQ context below.
Do not invent policies or details.
Keep the answer short and direct.
If the context does not answer the question, say:
"I don't know based on the available store information."

FAQ CONTEXT:
{chr(10).join(f"- {item}" for item in context)}

QUESTION:
{query}
"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_completion_tokens=300,
    )
    return response.choices[0].message.content.strip()


def faq_chain(query: str) -> str:
    context = _retrieve(query)
    return generate_answer(query, context)
