import logging

log = logging.getLogger(__name__)


class StepExecutor:

    def __init__(self, tool_router):

        self.tool_router = tool_router

    def execute(self, step, context):

        from desktop_agent.brain.safety_manager import SafetyManager

        safety = SafetyManager()
        tool = getattr(step, "tool", None) or getattr(step, "name", "unknown")
        args = getattr(step, "args", {}) or {}

        if not safety.check(tool, args):
            log.warning("[StepExecutor] BLOCKED by safety: tool=%s", tool)
            return {"ok": False, "error": f"Safety block: {tool}"}

        log.info("[StepExecutor] Executing: tool=%s", tool)
        return self.tool_router.execute(step)
