"""In-process publish/subscribe event bus and ordered audit log (OP-041).

EventBus — synchronous, FIFO-ordered pub/sub.  All subscribers for a given
event type are called in registration order before publish() returns.

AuditLog — ordered in-memory list of emitted chips.  Persisted to SQLite via
AuditEvent (UI-015); for OP-041 it serves as the in-process record.

Usage::

    from app.services.events import default_event_bus, default_audit_log

    def my_handler(chip):
        ...

    default_event_bus.subscribe('label_chip', my_handler)
    default_event_bus.publish('label_chip', chip)   # my_handler called immediately
    default_event_bus.unsubscribe('label_chip', my_handler)

    chips = default_audit_log.records   # ordered list of all emitted chips
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable


class EventBus:
    """Synchronous in-process pub/sub bus.

    Subscribers are called in FIFO registration order.  unsubscribe() is
    idempotent — removing a handler that was never registered is a no-op.
    """

    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[[Any], None]]] = defaultdict(list)

    def subscribe(self, event_type: str, callback: Callable[[Any], None]) -> None:
        self._subs[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[[Any], None]) -> None:
        try:
            self._subs[event_type].remove(callback)
        except ValueError:
            pass

    def publish(self, event_type: str, payload: Any) -> None:
        for cb in list(self._subs[event_type]):
            cb(payload)

    def clear(self, event_type: str | None = None) -> None:
        if event_type is None:
            self._subs.clear()
        else:
            self._subs[event_type].clear()


class AuditLog:
    """Ordered in-process log of emitted LabelChip records.

    Chips are appended in emission order (FIFO).  The list can be flushed
    to the SQLite AuditEvent table by UI-015's subscriber; for OP-041 it
    provides the in-process "persisted in audit log" guarantee.
    """

    def __init__(self) -> None:
        self._records: list[Any] = []

    def append(self, chip: Any) -> None:
        self._records.append(chip)

    @property
    def records(self) -> list[Any]:
        return list(self._records)

    def clear(self) -> None:
        self._records.clear()

    def __len__(self) -> int:
        return len(self._records)


default_event_bus: EventBus = EventBus()
default_audit_log: AuditLog = AuditLog()
