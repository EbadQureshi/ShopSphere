import atexit
import hashlib
import json
import queue
import subprocess
import sys
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
from groq import Groq
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models import ChatMessage, ChatSession, Product

PRODUCT_COLLECTION = "shopsphere_products_local_embeddings"
MAX_HISTORY_MESSAGES = 10
MAX_RETRIEVED_PRODUCTS = 5
EMBEDDING_WORKER_TIMEOUT_SECONDS = 300

_embedding_lock = threading.Lock()
_embedding_process = None
_embedding_responses = None


@lru_cache(maxsize=1)
def _groq_client(api_key: str) -> Groq:
    return Groq(api_key=api_key, timeout=90)


def _read_embedding_worker(process, responses: queue.Queue) -> None:
    if process.stdout is None:
        return
    for line in process.stdout:
        responses.put(line)


def _receive_embedding_response(process, responses: queue.Queue) -> dict[str, Any]:
    try:
        line = responses.get(timeout=EMBEDDING_WORKER_TIMEOUT_SECONDS)
    except queue.Empty as error:
        if process.poll() is not None:
            raise RuntimeError(
                f"Local embedding worker exited with status {process.returncode}."
            ) from error
        raise RuntimeError("Local embedding worker timed out.") from error
    try:
        response = json.loads(line)
    except json.JSONDecodeError as error:
        raise RuntimeError("Local embedding worker returned an invalid response.") from error
    if not isinstance(response, dict) or not response.get("ok"):
        detail = response.get("error", "Embedding operation failed.") if isinstance(response, dict) else "Invalid embedding response."
        raise RuntimeError(detail)
    return response


def _start_embedding_worker():
    backend_dir = Path(__file__).resolve().parents[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "app.embedding_worker"],
        cwd=backend_dir,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    responses: queue.Queue = queue.Queue()
    reader = threading.Thread(
        target=_read_embedding_worker,
        args=(process, responses),
        daemon=True,
    )
    reader.start()
    try:
        response = _receive_embedding_response(process, responses)
        if not response.get("ready"):
            raise RuntimeError("Local embedding worker did not initialize.")
    except Exception:
        process.terminate()
        process.wait()
        raise
    return process, responses


@lru_cache(maxsize=1)
def _collection(path: str):
    client = chromadb.PersistentClient(path=path)
    return client.get_or_create_collection(
        name=PRODUCT_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def _embed(texts: list[str]) -> list[list[float]]:
    global _embedding_process, _embedding_responses
    if not texts:
        return []
    with _embedding_lock:
        if _embedding_process is None or _embedding_process.poll() is not None:
            _embedding_process, _embedding_responses = _start_embedding_worker()
        if _embedding_process.stdin is None or _embedding_responses is None:
            raise RuntimeError("Local embedding worker is unavailable.")
        _embedding_process.stdin.write(json.dumps(texts) + "\n")
        _embedding_process.stdin.flush()
        response = _receive_embedding_response(
            _embedding_process,
            _embedding_responses,
        )
        embeddings = response.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise RuntimeError("Local embedding worker returned an invalid vector count.")
        return embeddings


def _stop_embedding_worker() -> None:
    if _embedding_process is not None and _embedding_process.poll() is None:
        _embedding_process.terminate()
        try:
            _embedding_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _embedding_process.kill()
            _embedding_process.wait()


atexit.register(_stop_embedding_worker)


def _product_document(product: Product) -> tuple[str, str, dict[str, Any]]:
    category = product.category.name if product.category else "Uncategorized"
    document = (
        f"Product: {product.name}\n"
        f"Category: {category}\n"
        f"Description: {product.description}\n"
        f"Price: ${product.price}\n"
        f"Stock: {product.stock}\n"
        f"Featured: {'yes' if product.is_featured else 'no'}"
    )
    content_hash = hashlib.sha256(document.encode("utf-8")).hexdigest()
    metadata = {
        "product_id": product.id,
        "name": product.name,
        "category": category,
        "price": str(product.price),
        "stock": product.stock,
        "content_hash": content_hash,
    }
    return str(product.id), document, metadata


def sync_product_index(db: Session):
    collection = _collection(str(settings.resolved_chroma_path))
    products = list(
        db.scalars(select(Product).options(joinedload(Product.category))).unique()
    )
    indexed = collection.get(include=["metadatas"])
    existing = {
        product_id: metadata
        for product_id, metadata in zip(indexed["ids"], indexed["metadatas"] or [])
    }
    active_ids = {str(product.id) for product in products}
    stale_ids = [product_id for product_id in existing if product_id not in active_ids]
    if stale_ids:
        collection.delete(ids=stale_ids)

    changed = []
    for product in products:
        product_id, document, metadata = _product_document(product)
        if existing.get(product_id, {}).get("content_hash") != metadata["content_hash"]:
            changed.append((product_id, document, metadata))

    if changed:
        documents = [item[1] for item in changed]
        collection.upsert(
            ids=[item[0] for item in changed],
            documents=documents,
            metadatas=[item[2] for item in changed],
            embeddings=_embed(documents),
        )
    return collection


def retrieve_products(collection, question: str) -> tuple[list[str], list[int]]:
    count = collection.count()
    if not count:
        return [], []
    results = collection.query(
        query_embeddings=_embed([question]),
        n_results=min(MAX_RETRIEVED_PRODUCTS, count),
        include=["documents", "metadatas"],
    )
    documents = (results["documents"] or [[]])[0]
    metadata = (results["metadatas"] or [[]])[0]
    product_ids = [
        int(item["product_id"])
        for item in metadata
        if item and item.get("product_id") is not None
    ]
    return [document for document in documents if document], product_ids


def generate_answer(
    question: str,
    products: list[str],
    history: list[ChatMessage],
) -> str:
    context = "\n\n".join(products) if products else "No matching product records were found."
    messages = [
        {
            "role": "system",
            "content": (
                "You are ShopSphere's shopping assistant. Answer the user's question using "
                "the product catalog context and this user's conversation only. Product "
                "details such as name, category, price, and stock must come from the "
                "provided catalog context. Never invent product facts. If the catalog "
                "does not provide an answer, say so clearly. Keep replies concise and "
                "helpful. Do not use Markdown, numbered lists, or repeat product cards "
                "in your reply; matching products are shown separately in the interface. "
                "Do not reveal another user's conversation or private data.\n\n"
                f"Product catalog context:\n{context}"
            ),
        }
    ]
    messages.extend(
        {"role": message.role, "content": message.content}
        for message in history[-MAX_HISTORY_MESSAGES:]
    )
    messages.append({"role": "user", "content": question})
    result = _groq_client(settings.groq_api_key).chat.completions.create(
        messages=messages,
        model=settings.groq_chat_model,
        max_tokens=400,
        temperature=0.2,
    )
    answer = result.choices[0].message.content
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("Hugging Face returned an empty chatbot response.")
    return answer.strip()


def get_or_create_chat_session(db: Session, user_id: int) -> ChatSession:
    session = db.scalar(select(ChatSession).where(ChatSession.user_id == user_id))
    if session is None:
        session = ChatSession(user_id=user_id)
        db.add(session)
        db.commit()
        db.refresh(session)
    return session
