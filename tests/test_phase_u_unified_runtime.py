"""Phase U — Unified System test suite.

Validates the ONE-MYRAA contracts:

- canonical AssistantRequest / AssistantResponse
- ONE task identity + lifecycle events on the ONE EventBus
- fast path stays fast (no SuperBrain for DIRECT_KNOWLEDGE / CONVERSATION)
- full pipeline delegates to SuperBrain (no second brain)
- every failure normalizes to the canonical F6 error envelope
- voice converges through the same runtime as text
- multi-agent skills plug into SuperBrain through the B19 engine seam

Hermetic: no container boot, no network, no desktop side effects.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from desktop_agent.brain.assistant_runtime import (  # noqa: E402
    AssistantRequest,
    AssistantResponse,
    AssistantRuntime,
    InputType,
    TaskState,
)
from desktop_agent.brain.blackboard.event_bus import EventBus  # noqa: E402


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

def make_super_brain(ok=True, message="done", raise_exc=None, spy=None):
    """Fake SuperBrain standing in for the planning/closed-loop authority."""

    def process(user_request, request_id=None, execution_depth="standard", route=None):
        if spy is not None:
            spy.append(
                {
                    "user_request": user_request,
                    "request_id": request_id,
                }
            )
        if raise_exc is not None:
            raise raise_exc
        return SimpleNamespace(
            success=ok,
            message=message,
            decision="EXECUTE",
            capability="DESKTOP_ENGINE",
            execution=SimpleNamespace(to_dict=lambda: {"steps": 1}),
        )

    return SimpleNamespace(process=process)


class Recorder:
    """Records EventBus events."""

    def __init__(self, bus: EventBus, *names: str):
        self.events: list = []
        for n in names:
            bus.subscribe(n, self._on)
        self._names = names

    def _on(self, evt):
        self.events.append((evt.name, dict(evt.payload)))

    def names(self):
        return [name for name, _payload in self.events]

    def payloads(self, name):
        return [p for n, p in self.events if n == name]


def make_runtime(super_brain=None, bus=None):
    bus = bus or EventBus()
    runtime = AssistantRuntime(
        super_brain=super_brain or make_super_brain(),
        event_bus=bus,
    )
    return runtime, bus


def make_request(text="open notepad", **kw):
    kw.setdefault("source", "unit_test")
    return AssistantRequest(user_input=text, **kw)


# ---------------------------------------------------------------------------
# 1. Canonical request / response contract
# ---------------------------------------------------------------------------

class TestRequestContract(unittest.TestCase):

    def test_request_defaults(self):
        req = AssistantRequest(user_input="hello")
        self.assertEqual(req.input_type, InputType.TEXT)
        self.assertEqual(req.source, "unknown")
        self.assertEqual(req.context, {})
        self.assertEqual(req.attachments, [])
        self.assertIsNone(req.task_id)

    def test_input_types_cover_modalities(self):
        for t in ("text", "voice", "vision", "image", "file", "document", "multimodal"):
            self.assertIn(t, [i.value for i in InputType])

    def test_normalized_input_strips(self):
        self.assertEqual(AssistantRequest(user_input="  hi  ").normalized_input(), "hi")

    def test_empty_input_is_canonical_error(self):
        runtime, _ = make_runtime()
        resp = runtime.handle(make_request(text="   "))
        self.assertIsInstance(resp, AssistantResponse)
        self.assertFalse(resp.ok)
        self.assertEqual(resp.error["category"], "invalid_request")
        self.assertTrue(resp.error["recoverable"])


# ---------------------------------------------------------------------------
# 2. Fast path — simple requests never touch SuperBrain
# ---------------------------------------------------------------------------

class TestFastPath(unittest.TestCase):

    def test_direct_knowledge_fast_answer(self):
        calls: list = []
        sb = make_super_brain(spy=calls)
        runtime, _ = make_runtime(super_brain=sb)
        resp = runtime.handle(make_request("What is Python?"))
        self.assertTrue(resp.ok)
        self.assertEqual(resp.decision, "FAST_ANSWER")
        self.assertEqual(resp.route, "TASK_ROUTER_FAST")
        # STALE EXPECTATION UPDATED (§61): the original assertion `message == ""`
        # encoded the P0 defect documented in PHASE_29_9 ("FAST_PATH returns
        # success=True, message='' without invoking model") which was FIXED to
        # stream a real Ollama answer. The fast path now returns actual text.
        self.assertTrue(resp.message and resp.message.strip())
        self.assertEqual(calls, [])         # SuperBrain NOT invoked

    def test_conversation_fast_answer(self):
        runtime, _ = make_runtime()
        resp = runtime.handle(make_request("Hello"))
        self.assertTrue(resp.ok)
        self.assertEqual(resp.decision, "FAST_ANSWER")


# ---------------------------------------------------------------------------
# 3. Full pipeline — one delegation, one task identity
# ---------------------------------------------------------------------------

class TestFullPipeline(unittest.TestCase):

    def test_action_task_goes_through_super_brain_once(self):
        calls: list = []
        sb = make_super_brain(spy=calls)
        runtime, _ = make_runtime(super_brain=sb)
        resp = runtime.handle(make_request("open notepad"))
        self.assertTrue(resp.ok)
        self.assertEqual(resp.route, "SUPER_BRAIN")
        self.assertEqual(len(calls), 1)     # exactly ONE planning authority
        # request lineage preserved end-to-end
        self.assertEqual(calls[0]["request_id"], resp.request_id)
        meta = resp.result["metadata"]
        self.assertEqual(meta["task_id"], resp.task_id)
        self.assertEqual(meta["route"], "SUPER_BRAIN")

    def test_task_id_propagates_when_supplied(self):
        runtime, _ = make_runtime()
        resp = runtime.handle(make_request("What is Python?", task_id="task-fixed"))
        self.assertEqual(resp.task_id, "task-fixed")
        self.assertEqual(resp.request_id, "task-fixed")

    def test_status_tracks_terminal_state(self):
        runtime, _ = make_runtime()
        resp = runtime.handle(make_request("open notepad"))
        snap = runtime.status(resp.task_id)
        self.assertIsNotNone(snap)
        self.assertEqual(snap["state"], TaskState.COMPLETED.value)


# ---------------------------------------------------------------------------
# 4. Event architecture — one bus, correlated lifecycle
# ---------------------------------------------------------------------------

class TestLifecycleEvents(unittest.TestCase):

    def test_event_sequence_with_correlation_ids(self):
        bus = EventBus()
        rec = Recorder(
            bus,
            "task.created",
            "task.classified",
            "task.started",
            "task.completed",
        )
        runtime, _ = make_runtime(bus=bus)
        resp = runtime.handle(make_request("open notepad"))

        self.assertEqual(
            rec.names(),
            [
                "task.created",
                "task.classified",
                "task.started",
                "task.completed",
            ],
        )
        for payload in rec.events:
            self.assertEqual(payload[1]["task_id"], resp.task_id)
            self.assertIn("timestamp", payload[1])
            self.assertEqual(payload[1]["source"], "unit_test")

    def test_fast_path_skips_started_event(self):
        bus = EventBus()
        rec = Recorder(bus, "task.started", "task.completed")
        runtime, _ = make_runtime(bus=bus)
        runtime.handle(make_request("Hello"))
        self.assertNotIn("task.started", rec.names())
        self.assertIn("task.completed", rec.names())


# ---------------------------------------------------------------------------
# 5. Error contract — every failure normalizes canonically
# ---------------------------------------------------------------------------

class TestErrorContract(unittest.TestCase):

    F6_KEYS = {"category", "severity", "message", "recoverable", "source"}

    def test_subsystem_exception_becomes_canonical_envelope(self):
        bus = EventBus()
        rec = Recorder(bus, "task.failed")
        sb = make_super_brain(raise_exc=RuntimeError("planner exploded"))
        runtime, _ = make_runtime(super_brain=sb, bus=bus)
        resp = runtime.handle(make_request("fix this bug"))

        self.assertFalse(resp.ok)
        self.assertIsNotNone(resp.error)
        self.F6_KEYS.issubset(set(resp.error.keys()))
        self.assertEqual(resp.error["task_id"], resp.task_id)
        self.assertEqual(rec.names(), ["task.failed"])

    def test_failed_superbrain_result_is_not_ok(self):
        runtime, _ = make_runtime(super_brain=make_super_brain(ok=False, message="blocked"))
        resp = runtime.handle(make_request("shutdown the pc"))
        self.assertFalse(resp.ok)
        self.assertIn("blocked", resp.message)


# ---------------------------------------------------------------------------
# 6. Cancellation model
# ---------------------------------------------------------------------------

class TestCancellation(unittest.TestCase):

    def test_unknown_task_cannot_be_cancelled(self):
        runtime, _ = make_runtime()
        out = runtime.cancel("task-does-not-exist")
        self.assertFalse(out["ok"])

    def test_checkpoint_honours_cancellation(self):
        bus = EventBus()
        rec = Recorder(bus, "task.cancelled")
        runtime, _ = make_runtime(bus=bus)

        original_classify = runtime._classify

        def classify_and_cancel(text):
            route = original_classify(text)
            runtime.cancel(
                # cancel the in-flight task at the checkpoint
                next(iter(runtime.active_tasks()))["task_id"]
                if runtime.active_tasks()
                else ""
            )
            return route

        runtime._classify = classify_and_cancel
        resp = runtime.handle(make_request("open notepad"))
        self.assertTrue(resp.cancelled)
        self.assertFalse(resp.ok)
        self.assertIn("task.cancelled", rec.names())


# ---------------------------------------------------------------------------
# 7. Voice convergence — SAME runtime, different modality
# ---------------------------------------------------------------------------

class TestVoiceConvergence(unittest.TestCase):

    def test_voice_loop_executes_through_assistant_runtime(self):
        from desktop_agent.speech.continuous_voice_loop import ContinuousVoiceLoop

        calls: list = []
        sb = make_super_brain(spy=calls, message="Opened Notepad")
        runtime, _ = make_runtime(super_brain=sb)
        loop = ContinuousVoiceLoop()

        def execute(transcript: str):
            resp = runtime.handle(
                AssistantRequest(
                    user_input=transcript,
                    input_type=InputType.VOICE,
                    source="continuous_voice_loop",
                )
            )
            return {
                "ok": bool(resp.ok),
                "message": resp.message,
                "decision": resp.decision,
                "task_id": resp.task_id,
                "request_id": resp.request_id,
            }

        loop.set_execute_callback(execute)
        out = loop.on_user_transcript("open notepad")

        self.assertTrue(out["ok"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(out["result"]["decision"], "EXECUTE")
        # the voice turn produced a speakable response for TTS extraction
        self.assertEqual(loop._extract_response_text(out["result"]), "Opened Notepad")

    def test_voice_duplicate_transcript_deduped(self):
        from desktop_agent.speech.continuous_voice_loop import ContinuousVoiceLoop

        runtime, _ = make_runtime()
        loop = ContinuousVoiceLoop()
        loop.set_execute_callback(lambda t: {"ok": True})
        first = loop.on_user_transcript("what time is it")
        second = loop.on_user_transcript("what time is it")
        self.assertTrue(first["ok"])
        self.assertEqual(second.get("error"), "duplicate_transcript")


# ---------------------------------------------------------------------------
# 8. Multi-agent skills plug into the ONE pipeline (B19 seam)
# ---------------------------------------------------------------------------

class TestMultiAgentCapabilityAdapter(unittest.TestCase):

    def test_successful_plan_maps_to_success(self):
        from desktop_agent.skills.capability_adapter import (
            CAPABILITY_ID,
            MultiAgentCapabilityEngine,
        )

        fake = SimpleNamespace(
            execute=lambda goal, ctx: {
                "status": "completed",
                "plan_id": "p1",
                "results": [{"summary": "built project"}],
            }
        )
        eng = MultiAgentCapabilityEngine(orchestrator=fake)
        goal = SimpleNamespace(text="build a python project")
        out = eng.execute(goal, {})
        self.assertTrue(out["success"])
        self.assertEqual(out["capability"], CAPABILITY_ID)
        self.assertIn("built project", out["message"])

    def test_failed_plan_maps_to_failure(self):
        from desktop_agent.skills.capability_adapter import MultiAgentCapabilityEngine

        fake = SimpleNamespace(
            execute=lambda goal, ctx: {"status": "failed", "error": "no workers"}
        )
        eng = MultiAgentCapabilityEngine(orchestrator=fake)
        out = eng.execute(SimpleNamespace(text="do everything"), {})
        self.assertFalse(out["success"])

    def test_orchestrator_exception_does_not_escape(self):
        from desktop_agent.skills.capability_adapter import MultiAgentCapabilityEngine

        def boom(goal, ctx):
            raise ValueError("worker crashed")

        eng = MultiAgentCapabilityEngine(orchestrator=SimpleNamespace(execute=boom))
        out = eng.execute(SimpleNamespace(text="x"), {})
        self.assertFalse(out["success"])
        self.assertIn("multi-agent error", out["message"])


if __name__ == "__main__":
    unittest.main()
