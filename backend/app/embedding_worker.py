import json
import sys

from app.core.config import settings


def _write_response(response: dict) -> None:
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


def main() -> int:
    try:
        from langchain_huggingface import HuggingFaceEmbeddings

        embeddings = HuggingFaceEmbeddings(
            model_name=settings.hf_embedding_model,
            model_kwargs={"device": "cpu", "token": settings.hf_token},
            encode_kwargs={"normalize_embeddings": True},
        )
    except Exception as error:
        _write_response(
            {"ok": False, "error": f"{type(error).__name__}: {error}"}
        )
        return 1

    _write_response({"ok": True, "ready": True})
    for line in sys.stdin:
        try:
            texts = json.loads(line)
            vectors = embeddings.embed_documents(texts)
            _write_response({"ok": True, "embeddings": vectors})
        except Exception as error:
            _write_response(
                {"ok": False, "error": f"{type(error).__name__}: {error}"}
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
