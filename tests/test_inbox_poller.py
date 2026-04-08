from types import SimpleNamespace

from app.services import inbox_poller


class _FakeDb:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def _message(external_message_id: str):
    return SimpleNamespace(channel="gmail", external_message_id=external_message_id)


def test_process_messages_rolls_back_failed_message_without_blocking_batch(monkeypatch):
    db = _FakeDb()

    def fake_process_incoming_message(_db, message):
        if message.external_message_id == "bad":
            raise RuntimeError("boom")
        if message.external_message_id == "duplicate":
            return {"status": "duplicate"}
        return {"status": "processed"}

    monkeypatch.setattr(inbox_poller, "process_incoming_message", fake_process_incoming_message)

    processed, duplicates, errors = inbox_poller._process_messages(
        db,
        [_message("ok-1"), _message("duplicate"), _message("bad"), _message("ok-2")],
    )

    assert processed == 2
    assert duplicates == 1
    assert errors == 1
    assert db.commits == 3
    assert db.rollbacks == 1
