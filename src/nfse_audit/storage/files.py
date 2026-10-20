"""Batch files on a volume shared by the API and the worker (claim check pattern).

The queue message carries only the batch id; the documents themselves live here.
Layout: <data_dir>/batches/<batch_id>/input/*  and  .../report.json
"""

import re
from collections.abc import Iterator
from pathlib import Path

from nfse_audit.pipeline import Document

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")
_BATCH_ID = re.compile(r"^[0-9a-f]{32}$")


def safe_filename(index: int, name: str) -> str:
    """Never trust an uploaded filename: "../../etc/passwd" becomes "0001_passwd"."""
    base = _UNSAFE.sub("_", Path(name.replace("\\", "/")).name).lstrip(".") or "document"
    return f"{index:04d}_{base}"


class BatchFileStore:
    def __init__(self, data_dir: Path) -> None:
        self._root = data_dir / "batches"

    def _batch_dir(self, batch_id: str) -> Path:
        if not _BATCH_ID.match(batch_id):
            raise ValueError(f"invalid batch id: {batch_id!r}")
        return self._root / batch_id

    def save_inputs(self, batch_id: str, documents: list[Document]) -> None:
        input_dir = self._batch_dir(batch_id) / "input"
        input_dir.mkdir(parents=True, exist_ok=True)
        for index, (name, content) in enumerate(documents, start=1):
            (input_dir / safe_filename(index, name)).write_bytes(content)

    def iter_inputs(self, batch_id: str) -> Iterator[Document]:
        input_dir = self._batch_dir(batch_id) / "input"
        for path in sorted(input_dir.iterdir()):
            original_name = path.name.split("_", 1)[1]
            yield original_name, path.read_bytes()

    def save_report(self, batch_id: str, report_json: str) -> None:
        path = self._batch_dir(batch_id) / "report.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(report_json, encoding="utf-8")
        tmp.replace(path)  # atomic: readers never see a half-written report

    def read_report(self, batch_id: str) -> str | None:
        path = self._batch_dir(batch_id) / "report.json"
        return path.read_text(encoding="utf-8") if path.exists() else None
