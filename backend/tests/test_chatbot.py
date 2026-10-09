import os
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.chatbot import (
    _plain_text_answer,
    generate_answer,
    retrieve_products,
    retrieval_query,
)
from app.models import ChatMessage
from app.schemas import ChatMessageOut, ChatSessionSummaryOut


class FakeCollection:
    def __init__(self, documents, metadatas, distances):
        self.documents = documents
        self.metadatas = metadatas
        self.distances = distances
        self.query_args = None

    def count(self):
        return len(self.documents)

    def query(self, **kwargs):
        self.query_args = kwargs
        return {
            "documents": [self.documents],
            "metadatas": [self.metadatas],
            "distances": [self.distances],
        }


class ChatbotRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.products = [
            (
                "Product: Wireless Headphones\nCategory: Headphones\n"
                "Description: Bluetooth over-ear audio\nPrice: $79.00\nStock: 8",
                {"product_id": 1, "name": "Wireless Headphones", "category": "Headphones", "price": "79.00", "stock": 8},
                0.25,
            ),
            (
                "Product: Gaming Keyboard\nCategory: Keyboards\n"
                "Description: Mechanical RGB keys\nPrice: $69.00\nStock: 4",
                {"product_id": 2, "name": "Gaming Keyboard", "category": "Keyboards", "price": "69.00", "stock": 4},
                0.18,
            ),
            (
                "Product: Wireless Earbuds\nCategory: Headphones\n"
                "Description: Compact Bluetooth earbuds\nPrice: $39.00\nStock: 0",
                {"product_id": 3, "name": "Wireless Earbuds", "category": "Headphones", "price": "39.00", "stock": 0},
                0.32,
            ),
            (
                "Product: Wireless Mouse\nCategory: Computer Mice\n"
                "Description: Bluetooth optical mouse\nPrice: $20.00\nStock: 6",
                {"product_id": 4, "name": "Wireless Mouse", "category": "Computer Mice", "price": "20.00", "stock": 6},
                0.10,
            ),
        ]

    def test_retrieval_excludes_unrelated_products_even_if_vector_ranked_first(self):
        collection = FakeCollection(
            [product[0] for product in self.products],
            [product[1] for product in self.products],
            [0.25, 0.55, 0.32, 0.10],
        )
        with patch("app.chatbot._embed", return_value=[[0.0]]):
            documents, product_ids = retrieve_products(collection, "wireless headphones")

        self.assertEqual(product_ids, [1, 3])
        self.assertEqual(len(documents), 2)
        self.assertEqual(collection.query_args["include"], ["documents", "metadatas", "distances"])

    def test_retrieval_applies_explicit_budget_and_stock_constraints(self):
        collection = FakeCollection(
            [product[0] for product in self.products],
            [product[1] for product in self.products],
            [0.25, 0.55, 0.32, 0.10],
        )
        with patch("app.chatbot._embed", return_value=[[0.0]]):
            _, product_ids = retrieve_products(
                collection,
                "wireless headphones under $50 available",
            )

        self.assertEqual(product_ids, [])

    def test_retrieval_uses_only_current_question_unless_it_is_a_follow_up(self):
        history = [
            ChatMessage(role="user", content="Show me wireless headphones"),
            ChatMessage(role="assistant", content="Here are the matching headphones."),
        ]
        self.assertEqual(retrieval_query("show me a keyboard", history), "show me a keyboard")
        self.assertEqual(
            retrieval_query("Is this laptop in stock?", history),
            "Is this laptop in stock?",
        )
        self.assertEqual(
            retrieval_query("Is it in stock?", history),
            "Show me wireless headphones\nIs it in stock?",
        )

    def test_answer_generation_scopes_prompt_to_catalog_and_current_request(self):
        client = Mock()
        completion = Mock()
        completion.choices = [
            SimpleNamespace(message=SimpleNamespace(content="It is in stock for $79.00."))
        ]
        client.chat.completions.create.return_value = completion
        product_context = "Product: Wireless Headphones\nPrice: $79.00\nStock: 8"

        with patch("app.chatbot._groq_client", return_value=client):
            answer = generate_answer("Is it in stock?", [product_context], [])

        self.assertEqual(answer, "It is in stock for $79.00.")
        request = client.chat.completions.create.call_args.kwargs
        self.assertEqual(request["temperature"], 0.1)
        self.assertIn("current user's product question", request["messages"][0]["content"])
        self.assertIn(product_context, request["messages"][0]["content"])
        self.assertIn("natural prose only", request["messages"][0]["content"])

    def test_product_markdown_list_becomes_professional_plain_sentence(self):
        answer = (
            "*   **Mens Casual Premium Slim Fit T-Shirts**\n"
            "    *   **Category:** Men's Tops\n"
            "    *   **Price:** $22.30\n"
            "    *   **Stock:** 10"
        )

        self.assertEqual(
            _plain_text_answer(answer),
            "The catalog lists Mens Casual Premium Slim Fit T-Shirts in Men's Tops "
            "at $22.30, with 10 in stock.",
        )

    def test_plain_text_normalizer_removes_common_markdown_markers(self):
        answer = _plain_text_answer("**Available now**\n\n- Let me know if you need help.")

        self.assertEqual(answer, "Available now\nLet me know if you need help.")
        self.assertNotRegex(answer, r"[*_`]")


class ChatTimestampTests(unittest.TestCase):
    def test_naive_database_timestamps_are_serialized_as_utc(self):
        timestamp = datetime(2026, 10, 9, 3, 40, 0)
        message = ChatMessageOut(
            id=1,
            role="user",
            content="hello",
            created_at=timestamp,
        )
        session = ChatSessionSummaryOut(
            id=1,
            preview="hello",
            updated_at=timestamp,
        )

        self.assertIn("2026-10-09T03:40:00Z", message.model_dump_json())
        self.assertIn("2026-10-09T03:40:00Z", session.model_dump_json())

    def test_aware_timestamps_are_normalized_to_utc(self):
        timestamp = datetime.fromisoformat("2026-10-09T08:40:00+05:00")
        message = ChatMessageOut(
            id=1,
            role="user",
            content="hello",
            created_at=timestamp,
        )

        self.assertIn(
            "2026-10-09T03:40:00Z",
            message.model_dump_json(),
        )


if __name__ == "__main__":
    unittest.main()
