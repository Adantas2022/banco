"""Dead Letter Queue middleware para Dramatiq.

Captura mensagens que esgotaram todas as tentativas de retry e:
1. Persiste na collection 'dead_letter_queue' do MongoDB para análise e reprocessamento
2. Atualiza o status do documento para FAILED
3. Registra métricas no Prometheus
"""

from datetime import datetime, timezone
from typing import Optional

from dramatiq.middleware import Middleware, SkipMessage

from irpf_processor.shared.logging import get_logger

logger = get_logger(__name__)


class DeadLetterQueueMiddleware(Middleware):

    def __init__(self, mongo_uri: str, mongo_db: str):
        self._mongo_uri = mongo_uri
        self._mongo_db = mongo_db
        self._client = None

    def _get_db(self):
        if self._client is None:
            from pymongo import MongoClient
            self._client = MongoClient(self._mongo_uri)
        return self._client[self._mongo_db]

    def after_skip_message(self, broker, message):
        """Called when a message is skipped after exhausting all retries."""
        actor_name = message.actor_name
        queue_name = message.queue_name
        message_id = message.message_id
        args = message.args
        kwargs = message.kwargs
        options = message.options

        retries = options.get("retries", 0)
        traceback_str = options.get("traceback", "")

        logger.error(
            "Message sent to DLQ after exhausting retries",
            actor_name=actor_name,
            queue_name=queue_name,
            message_id=message_id,
            retries=retries,
            args=str(args)[:500],
        )

        try:
            self._persist_to_dlq(message, retries, traceback_str)
        except Exception as e:
            logger.error("Failed to persist message to DLQ", error=str(e))

        try:
            self._mark_document_failed(message, actor_name)
        except Exception as e:
            logger.error("Failed to mark document as FAILED", error=str(e))

        try:
            self._record_metrics(actor_name, queue_name)
        except Exception:
            pass

    def _persist_to_dlq(
        self,
        message,
        retries: int,
        traceback_str: str,
    ) -> None:
        db = self._get_db()

        dlq_doc = {
            "message_id": message.message_id,
            "actor_name": message.actor_name,
            "queue_name": message.queue_name,
            "args": message.args,
            "kwargs": message.kwargs,
            "options": {
                k: v for k, v in message.options.items()
                if k not in ("trace_context",)
            },
            "retries_exhausted": retries,
            "traceback": traceback_str,
            "status": "pending_review",
            "created_at": datetime.now(timezone.utc),
            "resolved_at": None,
            "resolution": None,
        }

        document_id, tenant_id = self._extract_document_info(message)
        if document_id:
            dlq_doc["document_id"] = document_id
        if tenant_id:
            dlq_doc["tenant_id"] = tenant_id

        db["dead_letter_queue"].insert_one(dlq_doc)

        logger.info(
            "Message persisted to DLQ collection",
            message_id=message.message_id,
            document_id=document_id,
        )

    def _mark_document_failed(self, message, actor_name: str) -> None:
        document_id, tenant_id = self._extract_document_info(message)
        if not document_id or not tenant_id:
            return

        from irpf_processor.domain.enums import DocumentStatus

        db = self._get_db()
        error_msg = (
            f"Processing failed after exhausting all retries "
            f"(actor: {actor_name}, message_id: {message.message_id})"
        )

        db["documents"].update_one(
            {"document_id": document_id, "tenant_id": tenant_id},
            {"$set": {
                "status": DocumentStatus.FAILED.value,
                "error_message": error_msg,
                "dlq_message_id": message.message_id,
                "updated_at": datetime.now(timezone.utc),
            }},
        )

        logger.warning(
            "Document marked as FAILED due to DLQ",
            document_id=document_id,
            tenant_id=tenant_id,
            actor_name=actor_name,
        )

    def _extract_document_info(self, message) -> tuple[Optional[str], Optional[str]]:
        """Extrai document_id e tenant_id dos argumentos da mensagem.

        Todos os actors do pipeline seguem a assinatura (document_id, tenant_id).
        """
        args = message.args
        kwargs = message.kwargs

        document_id = None
        tenant_id = None

        if len(args) >= 1:
            document_id = args[0]
        if len(args) >= 2:
            tenant_id = args[1]

        if not document_id:
            document_id = kwargs.get("document_id")
        if not tenant_id:
            tenant_id = kwargs.get("tenant_id")

        return document_id, tenant_id

    def _record_metrics(self, actor_name: str, queue_name: str) -> None:
        from irpf_processor.shared.metrics import DLQ_MESSAGES_TOTAL
        DLQ_MESSAGES_TOTAL.labels(
            actor_name=actor_name,
            queue_name=queue_name,
        ).inc()
