import uuid
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, Response, UploadFile, status
from pydantic import BaseModel

from nfse_audit.api.dependencies import FileStoreDep, QueueDep, SettingsDep, StatusStoreDep
from nfse_audit.reporting import BatchReport, to_excel
from nfse_audit.storage import BatchState, BatchStatus

router = APIRouter()

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class BatchAccepted(BaseModel):
    batch_id: str
    state: BatchState
    status_url: str


class ReportFormat(StrEnum):
    JSON = "json"
    XLSX = "xlsx"


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/batches", status_code=status.HTTP_202_ACCEPTED)
async def create_batch(
    files: list[UploadFile],
    request: Request,
    settings: SettingsDep,
    status_store: StatusStoreDep,
    file_store: FileStoreDep,
    queue: QueueDep,
    idempotency_key: Annotated[str | None, Header(max_length=128)] = None,
) -> BatchAccepted:
    """Receive a batch of NFS-e documents and queue it. Returns 202 with the batch id."""
    if len(files) > settings.max_files_per_batch:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"at most {settings.max_files_per_batch} files per batch",
        )

    batch_id = uuid.uuid4().hex
    if idempotency_key:
        bound = status_store.claim_idempotency_key(
            idempotency_key, batch_id, settings.idempotency_ttl_seconds
        )
        if bound != batch_id:  # same request already received: return the original batch
            existing = status_store.get(bound)
            return _accepted(request, bound, existing.state if existing else BatchState.QUEUED)

    documents = []
    for upload in files:
        content = await upload.read(settings.max_file_bytes + 1)
        if len(content) > settings.max_file_bytes:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE,
                f"{upload.filename}: larger than {settings.max_file_bytes} bytes",
            )
        documents.append((upload.filename or "document", content))

    file_store.save_inputs(batch_id, documents)
    status_store.create(batch_id, documents=len(documents))
    queue.enqueue_batch(batch_id)
    return _accepted(request, batch_id, BatchState.QUEUED)


@router.get("/batches/{batch_id}")
def get_batch(batch_id: str, status_store: StatusStoreDep) -> BatchStatus:
    return _status_or_404(status_store, batch_id)


@router.get("/batches/{batch_id}/report")
def get_report(
    batch_id: str,
    status_store: StatusStoreDep,
    file_store: FileStoreDep,
    format: ReportFormat = ReportFormat.JSON,
) -> Response:
    batch = _status_or_404(status_store, batch_id)
    if batch.state is not BatchState.DONE:
        raise HTTPException(status.HTTP_409_CONFLICT, f"batch is {batch.state.value}")
    report_json = file_store.read_report(batch_id)
    if report_json is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")
    if format is ReportFormat.JSON:
        return Response(report_json, media_type="application/json")
    workbook = to_excel(BatchReport.model_validate_json(report_json))
    return Response(
        workbook,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="audit-{batch_id}.xlsx"'},
    )


def _status_or_404(status_store: StatusStoreDep, batch_id: str) -> BatchStatus:
    batch = status_store.get(batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "batch not found")
    return batch


def _accepted(request: Request, batch_id: str, state: BatchState) -> BatchAccepted:
    return BatchAccepted(
        batch_id=batch_id,
        state=state,
        status_url=str(request.url_for("get_batch", batch_id=batch_id)),
    )
