import fakeredis
import pytest

from nfse_audit.storage import BatchFileStore, BatchState, BatchStatusStore
from nfse_audit.storage.files import safe_filename

BATCH = "a" * 32


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("nota.xml", "0001_nota.xml"),
        ("../../etc/passwd", "0001_passwd"),
        ("..\\..\\windows\\win.ini", "0001_win.ini"),
        ("nota fiscal (1).xml", "0001_nota_fiscal__1_.xml"),
        (".hidden", "0001_hidden"),
        ("", "0001_document"),
    ],
)
def test_safe_filename_blocks_path_traversal(name, expected):
    assert safe_filename(1, name) == expected


def test_file_store_round_trip(tmp_path):
    store = BatchFileStore(tmp_path)
    store.save_inputs(BATCH, [("b.xml", b"2"), ("a.xml", b"1")])
    assert list(store.iter_inputs(BATCH)) == [("b.xml", b"2"), ("a.xml", b"1")]
    assert store.read_report(BATCH) is None
    store.save_report(BATCH, "{}")
    assert store.read_report(BATCH) == "{}"


def test_file_store_rejects_invalid_batch_id(tmp_path):
    with pytest.raises(ValueError):
        BatchFileStore(tmp_path).save_inputs("../escape", [])


def test_status_lifecycle():
    store = BatchStatusStore(fakeredis.FakeRedis())
    store.create(BATCH, documents=2)
    store.update(BATCH, BatchState.DONE, summary={"invoices_ok": 2})
    status = store.get(BATCH)
    assert (status.state, status.summary) == (BatchState.DONE, {"invoices_ok": 2})


def test_idempotency_key_is_bound_once():
    store = BatchStatusStore(fakeredis.FakeRedis())
    assert store.claim_idempotency_key("k", "batch-1", 60) == "batch-1"
    assert store.claim_idempotency_key("k", "batch-2", 60) == "batch-1"
