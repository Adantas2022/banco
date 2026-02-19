import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

DLQ_MODULE_PATH = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "irpf_processor"
    / "presentation"
    / "workers"
    / "dlq_middleware.py"
)


def _load_dlq_class():
    """Load DeadLetterQueueMiddleware directly from file, bypassing workers __init__.py."""
    spec = importlib.util.spec_from_file_location(
        "dlq_middleware", str(DLQ_MODULE_PATH)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.DeadLetterQueueMiddleware


def _make_middleware():
    cls = _load_dlq_class()
    return cls(
        mongo_uri="mongodb://localhost:27017",
        mongo_db="irpf_processor_test",
    )


def _make_message(
    actor_name="process_document",
    queue_name="default",
    message_id="msg-123",
    args=("doc-456", "tenant-789"),
    kwargs=None,
    retries=3,
    traceback="Traceback: SomeError",
):
    msg = MagicMock()
    msg.actor_name = actor_name
    msg.queue_name = queue_name
    msg.message_id = message_id
    msg.args = list(args)
    msg.kwargs = kwargs or {}
    msg.options = {
        "retries": retries,
        "traceback": traceback,
        "trace_context": {"traceparent": "should-be-excluded"},
    }
    return msg


class TestDeadLetterQueueMiddleware:

    def test_after_skip_message_persists_to_mongodb(self):
        middleware = _make_middleware()
        message = _make_message()

        mock_collection = MagicMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        with patch.object(middleware, "_get_db", return_value=mock_db):
            with patch.object(middleware, "_record_metrics"):
                middleware.after_skip_message(MagicMock(), message)

        insert_calls = mock_collection.insert_one.call_args_list
        assert len(insert_calls) == 1

        dlq_doc = insert_calls[0][0][0]
        assert dlq_doc["message_id"] == "msg-123"
        assert dlq_doc["actor_name"] == "process_document"
        assert dlq_doc["queue_name"] == "default"
        assert dlq_doc["document_id"] == "doc-456"
        assert dlq_doc["tenant_id"] == "tenant-789"
        assert dlq_doc["retries_exhausted"] == 3
        assert dlq_doc["traceback"] == "Traceback: SomeError"
        assert dlq_doc["status"] == "pending_review"
        assert "trace_context" not in dlq_doc["options"]

    def test_after_skip_message_marks_document_failed(self):
        middleware = _make_middleware()
        message = _make_message()

        mock_collection = MagicMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        with patch.object(middleware, "_get_db", return_value=mock_db):
            with patch.object(middleware, "_record_metrics"):
                middleware.after_skip_message(MagicMock(), message)

        update_calls = mock_collection.update_one.call_args_list
        assert len(update_calls) == 1

        filter_arg = update_calls[0][0][0]
        assert filter_arg == {"document_id": "doc-456", "tenant_id": "tenant-789"}

        update_arg = update_calls[0][0][1]
        set_fields = update_arg["$set"]
        assert set_fields["status"] == "FAILED"
        assert "dlq_message_id" in set_fields
        assert "error_message" in set_fields
        assert "updated_at" in set_fields

    def test_extract_document_info_from_args(self):
        middleware = _make_middleware()
        message = _make_message(args=("doc-abc", "tenant-xyz"))

        doc_id, tenant_id = middleware._extract_document_info(message)
        assert doc_id == "doc-abc"
        assert tenant_id == "tenant-xyz"

    def test_extract_document_info_from_kwargs(self):
        middleware = _make_middleware()
        message = _make_message(
            args=(),
            kwargs={"document_id": "doc-kw", "tenant_id": "tenant-kw"},
        )

        doc_id, tenant_id = middleware._extract_document_info(message)
        assert doc_id == "doc-kw"
        assert tenant_id == "tenant-kw"

    def test_extract_document_info_missing(self):
        middleware = _make_middleware()
        message = _make_message(args=(), kwargs={})

        doc_id, tenant_id = middleware._extract_document_info(message)
        assert doc_id is None
        assert tenant_id is None

    def test_skip_document_update_when_no_document_info(self):
        middleware = _make_middleware()
        message = _make_message(args=(), kwargs={})

        mock_dlq_collection = MagicMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_dlq_collection)

        with patch.object(middleware, "_get_db", return_value=mock_db):
            with patch.object(middleware, "_record_metrics"):
                middleware.after_skip_message(MagicMock(), message)

        mock_dlq_collection.insert_one.assert_called_once()
        mock_dlq_collection.update_one.assert_not_called()

    def test_persist_failure_does_not_crash_middleware(self):
        middleware = _make_middleware()
        message = _make_message()

        with patch.object(
            middleware, "_get_db", side_effect=Exception("MongoDB down")
        ):
            with patch.object(middleware, "_record_metrics"):
                middleware.after_skip_message(MagicMock(), message)

    def test_mark_failed_failure_does_not_crash_middleware(self):
        middleware = _make_middleware()
        message = _make_message()

        mock_dlq_collection = MagicMock()
        mock_doc_collection = MagicMock()
        mock_doc_collection.update_one.side_effect = Exception("Update failed")

        call_count = {"n": 0}
        def get_collection(name):
            call_count["n"] += 1
            if name == "dead_letter_queue":
                return mock_dlq_collection
            return mock_doc_collection

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(side_effect=get_collection)

        with patch.object(middleware, "_get_db", return_value=mock_db):
            with patch.object(middleware, "_record_metrics"):
                middleware.after_skip_message(MagicMock(), message)

        mock_dlq_collection.insert_one.assert_called_once()

    def test_ocr_worker_message_handled(self):
        middleware = _make_middleware()
        message = _make_message(
            actor_name="process_ocr_document",
            queue_name="extraction-ocr",
            args=("ocr-doc-1", "ocr-tenant-1"),
        )

        mock_collection = MagicMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        with patch.object(middleware, "_get_db", return_value=mock_db):
            with patch.object(middleware, "_record_metrics"):
                middleware.after_skip_message(MagicMock(), message)

        insert_calls = mock_collection.insert_one.call_args_list
        dlq_doc = insert_calls[0][0][0]
        assert dlq_doc["actor_name"] == "process_ocr_document"
        assert dlq_doc["document_id"] == "ocr-doc-1"

    def test_router_worker_message_handled(self):
        middleware = _make_middleware()
        message = _make_message(
            actor_name="route_document",
            queue_name="extraction-router",
            args=("route-doc-1", "route-tenant-1"),
        )

        mock_collection = MagicMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        with patch.object(middleware, "_get_db", return_value=mock_db):
            with patch.object(middleware, "_record_metrics"):
                middleware.after_skip_message(MagicMock(), message)

        insert_calls = mock_collection.insert_one.call_args_list
        dlq_doc = insert_calls[0][0][0]
        assert dlq_doc["actor_name"] == "route_document"
        assert dlq_doc["queue_name"] == "extraction-router"
        assert dlq_doc["document_id"] == "route-doc-1"

    def test_lazy_mongo_client_initialization(self):
        middleware = _make_middleware()
        assert middleware._client is None

        mock_client = MagicMock()
        mock_client.__getitem__ = MagicMock(return_value=MagicMock())

        with patch("pymongo.MongoClient", return_value=mock_client):
            middleware._get_db()
            assert middleware._client is mock_client

            middleware._get_db()
            assert middleware._client is mock_client
