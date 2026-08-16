import os
import re
import sqlite3
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db.sqlite"
TABLE_COLUMNS = (
    "product_link, title, brand, price, discount, avg_rating, total_ratings"
)


def _connect():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Product database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _clean_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _extract_number(query: str, pattern: str):
    match = re.search(pattern, query, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _detect_limit(query: str) -> int:
    match = re.search(r"\b(?:top|first|show|find|give)\s+(\d+)\b", query, re.I)
    if match:
        return max(1, min(int(match.group(1)), 20))
    return 5


def build_product_query(question: str) -> tuple[str, list]:
    q = question.lower().strip()
    conditions: list[str] = []
    params: list = []

    # Brand matching uses a parameterized LIKE, so user text never becomes SQL.
    brands = [
        "nike", "puma", "adidas", "campus", "skechers", "red tape",
        "sparx", "reebok", "asics", "fila", "bata", "hrx",
        "new balance", "brooks", "aadi", "fabbmate", "asian",
        "mactree", "bersache",
    ]
    for brand in brands:
        if brand in q:
            conditions.append("LOWER(brand) LIKE ?")
            params.append(f"%{brand}%")
            break

    # Generic product/category terms.
    category_terms = []
    for term in ("shoe", "shoes", "sneaker", "sneakers", "running", "walking", "sports"):
        if re.search(rf"\b{re.escape(term)}\b", q):
            category_terms.append(term.rstrip("s"))
    if category_terms:
        # Search the title for the most relevant category phrase.
        conditions.append(
            "(" + " OR ".join(["LOWER(title) LIKE ?" for _ in category_terms]) + ")"
        )
        params.extend([f"%{term}%" for term in category_terms])

    # Price constraints.
    under = _extract_number(q, r"(?:under|below|less than|up to)\s*(?:rs\.?|₹|rupees)?\s*([\d,]+)")
    if under is not None:
        conditions.append("price <= ?")
        params.append(under)

    above = _extract_number(q, r"(?:above|over|more than|greater than)\s*(?:rs\.?|₹|rupees)?\s*([\d,]+)")
    if above is not None:
        conditions.append("price >= ?")
        params.append(above)

    between = re.search(
        r"between\s*(?:rs\.?|₹|rupees)?\s*([\d,]+)\s*(?:and|-)\s*(?:rs\.?|₹|rupees)?\s*([\d,]+)",
        q,
        re.I,
    )
    if between:
        low = float(between.group(1).replace(",", ""))
        high = float(between.group(2).replace(",", ""))
        if low > high:
            low, high = high, low
        conditions.extend(["price >= ?", "price <= ?"])
        params.extend([low, high])

    # Discount constraints. Dataset stores 0.50 as 50%.
    discount = _extract_number(q, r"(?:at least|minimum|min)\s*(\d+(?:\.\d+)?)\s*%?\s*(?:discount)?")
    if discount is not None and ("discount" in q or "%" in q):
        conditions.append("discount >= ?")
        params.append(discount / 100)

    exact_discount = _extract_number(q, r"(\d+(?:\.\d+)?)\s*%\s*discount")
    if exact_discount is not None:
        conditions.append("discount >= ?")
        params.append(exact_discount / 100)

    rating = _extract_number(q, r"(?:rating|rated)\s*(?:above|over|at least)?\s*(\d(?:\.\d+)?)")
    if rating is not None:
        conditions.append("avg_rating >= ?")
        params.append(rating)

    # Ordering.
    if "discount" in q or "deal" in q or "offer" in q:
        order = "discount DESC"
    elif "cheapest" in q or "lowest price" in q or "cheap" in q:
        order = "price ASC"
    elif "expensive" in q or "highest price" in q:
        order = "price DESC"
    elif "rating" in q or "rated" in q or "best" in q:
        order = "avg_rating DESC, total_ratings DESC"
    else:
        order = "avg_rating DESC, total_ratings DESC"

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    limit = _detect_limit(q)

    sql = (
        f"SELECT {TABLE_COLUMNS} "
        f"FROM product{where} "
        f"ORDER BY {order} "
        f"LIMIT {limit}"
    )
    return sql, params


def _run_query(question: str) -> pd.DataFrame:
    query, params = build_product_query(question)

    print("\n[PRODUCT SEARCH]")
    print("SQL:", query)
    print("PARAMS:", params)

    with _connect() as conn:
        return pd.read_sql_query(query, conn, params=params)


def _product_dict(row: pd.Series) -> dict:
    discount = float(row.get("discount") or 0)
    if discount <= 1:
        discount *= 100

    return {
        "product_link": _clean_text(row.get("product_link")),
        "title": _clean_text(row.get("title")),
        "brand": _clean_text(row.get("brand")),
        "price": int(float(row.get("price") or 0)),
        "discount": round(discount, 2),
        "avg_rating": round(float(row.get("avg_rating") or 0), 2),
        "total_ratings": int(float(row.get("total_ratings") or 0)),
    }


def _fallback_answer(products: list[dict]) -> str:
    if not products:
        return "I couldn't find any products matching your request."

    if len(products) == 1:
        return f"I found 1 product matching your request: **{products[0]['title']}**."

    return f"I found **{len(products)} products** matching your request."


def _generate_answer(question: str, products: list[dict]) -> str:
    if not products:
        return "I couldn't find any products matching your request."

    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        return _fallback_answer(products)

    client = Groq(api_key=key)
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    compact = "\n".join(
        f"{i}. {p['title']} | Brand: {p['brand']} | "
        f"Price: Rs. {p['price']} | Discount: {p['discount']}% | "
        f"Rating: {p['avg_rating']}/5"
        for i, p in enumerate(products, 1)
    )

    prompt = f"""
You are ShopAI, an e-commerce shopping assistant.

Answer the user's question using ONLY these search results.
Do not invent information and do not mention SQL, databases, prompts, or AI internals.
Keep it concise. Mention the most useful product details.

QUESTION:
{question}

SEARCH RESULTS:
{compact}
"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_completion_tokens=500,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        print(f"[GROQ ANSWER FALLBACK] {type(exc).__name__}: {exc}")
        return _fallback_answer(products)


def sql_chain(question: str) -> tuple[str, list[dict]]:
    dataframe = _run_query(question)

    products = [_product_dict(row) for _, row in dataframe.iterrows()]
    answer = _generate_answer(question, products)

    return answer, products


# Backwards-compatible helpers for testing/debugging.
def run_query(query: str) -> pd.DataFrame:
    if not query.strip().lower().startswith("select"):
        raise ValueError("Only SELECT queries are allowed.")
    if ";" in query.rstrip(";"):
        raise ValueError("Multiple SQL statements are not allowed.")
    with _connect() as conn:
        return pd.read_sql_query(query.rstrip(";"), conn)


def generate_sql_query(question: str) -> str:
    query, params = build_product_query(question)
    # This helper returns the SQL only, mainly for debugging.
    return query
