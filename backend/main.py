import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from faq import faq_chain, ingest_faq_data
from router import route_query
from sql import sql_chain

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ingest_faq_data()
    yield


app = FastAPI(
    title="ShopAI E-commerce Chatbot API",
    version="2.0.0",
)

frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        frontend_url,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    answer: str
    route: str
    products: list[dict] = []


@app.get("/")
def root():
    return {"message": "ShopAI API is running", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    query = request.query.strip()

    try:
        route = route_query(query)

        if route == "faq":
            answer = faq_chain(query)
            return ChatResponse(answer=answer, route="faq", products=[])

        answer, products = sql_chain(query)
        return ChatResponse(
            answer=answer,
            route="sql",
            products=products,
        )

    except Exception as exc:
        print(f"[CHAT ERROR] {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong while processing your request.",
        ) from exc
