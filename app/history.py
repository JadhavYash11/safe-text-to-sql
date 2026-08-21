"""In-process history plus a durable feedback log for future eval cases."""

from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock
from uuid import uuid4

from app.models import FeedbackRequest, HistoryEntry


class QueryHistory:
    def __init__(self, max_entries: int = 100):
        self._entries: deque[HistoryEntry] = deque(maxlen=max_entries)
        self._lock = Lock()

    def add(self, question: str, sql: str, confidence: float, row_count: int, status: str) -> None:
        entry = HistoryEntry(
            id=str(uuid4()),
            timestamp=datetime.now(timezone.utc),
            question=question,
            sql=sql,
            confidence=confidence,
            row_count=row_count,
            status=status,
        )
        with self._lock:
            self._entries.appendleft(entry)

    def list(self) -> list[HistoryEntry]:
        with self._lock:
            return list(self._entries)


def persist_feedback(feedback: FeedbackRequest) -> None:
    """Incorrect feedback becomes source material for the evaluation suite."""
    path = Path("data/feedback.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"submitted_at": datetime.now(timezone.utc).isoformat(), **feedback.model_dump()}
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")

