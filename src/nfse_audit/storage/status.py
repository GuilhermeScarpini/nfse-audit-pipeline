"""Batch status in Redis, plus Idempotency-Key -> batch id mapping."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel
from redis import Redis


class BatchState(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class BatchStatus(BaseModel):
    batch_id: str
    state: BatchState
    documents: int
    created_at: datetime
    updated_at: datetime
    summary: dict[str, int] | None = None
    error: str | None = None


class BatchStatusStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @staticmethod
    def _key(batch_id: str) -> str:
        return f"nfse:batch:{batch_id}"

    def create(self, batch_id: str, documents: int) -> BatchStatus:
        now = datetime.now(UTC)
        status = BatchStatus(
            batch_id=batch_id,
            state=BatchState.QUEUED,
            documents=documents,
            created_at=now,
            updated_at=now,
        )
        self._redis.set(self._key(batch_id), status.model_dump_json())
        return status

    def get(self, batch_id: str) -> BatchStatus | None:
        raw = self._redis.get(self._key(batch_id))
        return BatchStatus.model_validate_json(raw) if raw else None  # type: ignore[arg-type]

    def update(
        self,
        batch_id: str,
        state: BatchState,
        *,
        summary: dict[str, int] | None = None,
        error: str | None = None,
    ) -> BatchStatus:
        current = self.get(batch_id)
        if current is None:
            raise KeyError(batch_id)
        updated = current.model_copy(
            update={
                "state": state,
                "updated_at": datetime.now(UTC),
                "summary": summary,
                "error": error,
            }
        )
        self._redis.set(self._key(batch_id), updated.model_dump_json())
        return updated

    def claim_idempotency_key(self, key: str, batch_id: str, ttl_seconds: int) -> str:
        """Atomically bind key -> batch_id. Returns the batch id already bound, if any.

        SET NX ("set if not exists") is atomic in Redis, so two identical requests
        arriving at the same time cannot both create a batch.
        """
        redis_key = f"nfse:idempotency:{key}"
        if self._redis.set(redis_key, batch_id, nx=True, ex=ttl_seconds):
            return batch_id
        existing = self._redis.get(redis_key)
        return existing.decode() if isinstance(existing, bytes) else str(existing)
