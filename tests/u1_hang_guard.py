"""U.1 hang-detection utility: bounded execution with diagnostic stack dump.

Usage:
    result = bounded(fn, args=(x,), timeout_s=10, label="summary()")

If fn does not finish within timeout_s, ALL thread stacks are dumped to
stderr (faulthandler) and AssertionError is raised identifying the blocked
call — tests FAIL diagnostically instead of hanging pytest forever.

The abandoned worker is a daemon thread so a genuinely deadlocked call can
never block test-suite completion.
"""

from __future__ import annotations

import faulthandler
import sys
import threading
from typing import Any, Callable


def bounded(
    fn: Callable[..., Any],
    args: tuple = (),
    kwargs: dict | None = None,
    timeout_s: float = 10.0,
    label: str = "",
) -> Any:
    """Run fn(*args, **kwargs) with a hard wall-clock bound."""
    kwargs = kwargs or {}
    outcome: dict[str, Any] = {"result": None, "exc": None}
    done = threading.Event()

    def _runner() -> None:
        try:
            outcome["result"] = fn(*args, **kwargs)
        except BaseException as exc:  # noqa: BLE001 — propagate to assert site
            outcome["exc"] = exc
        finally:
            done.set()

    worker = threading.Thread(
        target=_runner,
        name=f"bounded[{label or getattr(fn, '__name__', 'call')}]",
        daemon=True,
    )
    worker.start()

    if not done.wait(timeout_s):
        sys.stderr.write(f"\n=== HANG GUARD: '{label or fn}' exceeded {timeout_s}s ===\n")
        faulthandler.dump_traceback(file=sys.stderr)
        sys.stderr.write(f"=== END HANG GUARD ({label}) ===\n")
        raise AssertionError(
            f"Bounded execution exceeded {timeout_s}s in "
            f"'{label or getattr(fn, '__name__', fn)}' — probable deadlock "
            f"(stacks dumped above)."
        )

    if outcome["exc"] is not None:
        raise outcome["exc"]
    return outcome["result"]
