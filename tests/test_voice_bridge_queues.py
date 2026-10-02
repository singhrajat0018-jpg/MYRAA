"""Bridge fan-out queue bounds (Phase 9/10 debt item).

Control lifecycle events must NEVER drop; high-volume audio/partial events
drop oldest beyond MEDIA_MAX instead of growing without limit. Pure unit
tests over _BridgeEventQueues — no sockets, no Gemini.
"""
from __future__ import annotations

import asyncio
import types as _t


def _ev(kind, **data):
    return _t.SimpleNamespace(kind=kind, data=dict(data))


def _queues():
    from desktop_agent.main import _BridgeEventQueues

    return _BridgeEventQueues()


def test_media_bounded_drop_oldest_with_counter():
    qs = _queues()

    async def go():
        for i in range(qs.MEDIA_MAX + 72):
            await qs.put(_ev("audio", seq=i))

    asyncio.run(go())
    assert qs.media.qsize() == qs.MEDIA_MAX
    assert qs.dropped_media == 72
    # Oldest dropped: front of queue is seq 72.
    first = qs.media.get_nowait()
    assert first.data["seq"] == 72


def test_partial_counts_as_media():
    qs = _queues()

    async def go():
        for i in range(qs.MEDIA_MAX + 5):
            await qs.put(_ev("partial", seq=i))

    asyncio.run(go())
    assert qs.media.qsize() == qs.MEDIA_MAX
    assert qs.dropped_media == 5


def test_control_events_never_drop():
    qs = _queues()
    kinds = ["connection_failed", "error", "interrupted", "turn_complete",
             "reconnecting", "reconnected", "session_started", "connected",
             "go_away", "tool_result", "resumption", "closed"]

    async def go():
        for _ in range(3):
            for k in kinds:
                await qs.put(_ev(k))

    asyncio.run(go())
    assert qs.control.qsize() == 3 * len(kinds)
    assert qs.dropped_media == 0
    # FIFO order preserved.
    got = [qs.control.get_nowait().kind for _ in range(len(kinds))]
    assert got == kinds


def test_control_unaffected_by_media_flood():
    qs = _queues()

    async def go():
        for i in range(2 * qs.MEDIA_MAX):
            await qs.put(_ev("audio", seq=i))
        await qs.put(_ev("turn_complete", turn_id="T9"))
        await qs.put(_ev("connection_failed", reason="x"))

    asyncio.run(go())
    assert qs.media.qsize() == qs.MEDIA_MAX
    assert qs.control.qsize() == 2
    assert qs.control.get_nowait().data["turn_id"] == "T9"
