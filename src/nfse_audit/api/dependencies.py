"""Dependency providers for FastAPI's Depends().

Routes ask for what they need ("give me a status store") instead of building it.
Tests swap any provider with app.dependency_overrides, e.g. a fake queue.
"""

from functools import lru_cache
from typing import Annotated, Protocol

from fastapi import Depends
from redis import Redis
from rq import Queue, Retry

from nfse_audit.config import Settings, get_settings
from nfse_audit.storage import BatchFileStore, BatchStatusStore


class BatchQueue(Protocol):
    def enqueue_batch(self, batch_id: str) -> None: ...


class RqBatchQueue:
    def __init__(self, redis: Redis, settings: Settings) -> None:
        self._queue = Queue(settings.queue_name, connection=redis)
        self._timeout = settings.job_timeout_seconds

    def enqueue_batch(self, batch_id: str) -> None:
        self._queue.enqueue(
            "nfse_audit.worker.tasks.process_batch",
            batch_id,
            job_id=f"batch-{batch_id}",  # the same batch is never queued twice
            job_timeout=self._timeout,
            retry=Retry(max=3, interval=[10, 30, 60]),
        )


SettingsDep = Annotated[Settings, Depends(get_settings)]


@lru_cache
def _redis(url: str) -> Redis:
    return Redis.from_url(url)


def get_redis(settings: SettingsDep) -> Redis:
    return _redis(settings.redis_url)


def get_status_store(redis: Annotated[Redis, Depends(get_redis)]) -> BatchStatusStore:
    return BatchStatusStore(redis)


def get_file_store(settings: SettingsDep) -> BatchFileStore:
    return BatchFileStore(settings.data_dir)


def get_queue(redis: Annotated[Redis, Depends(get_redis)], settings: SettingsDep) -> BatchQueue:
    return RqBatchQueue(redis, settings)


StatusStoreDep = Annotated[BatchStatusStore, Depends(get_status_store)]
FileStoreDep = Annotated[BatchFileStore, Depends(get_file_store)]
QueueDep = Annotated[BatchQueue, Depends(get_queue)]
