"""
MYRAA Desktop Control Agent — Central tool registry.

Each tool module registers handlers into a flat dict `TOOLS` mapping
tool_name -> callable(args: dict) -> dict.

Handlers return a plain dict, typically {"result": "<status string>"}.
Errors should raise ToolError(message) so main.py can map them to {error}.
Shared singletons (UniversalController, confirmation store, etc.) live
on the `State` object so handlers stay stateless and easy to test.
"""

from __future__ import annotations

import importlib
import sys
import threading
from typing import Any, Callable, Dict

# Import permission configuration
from .config.permissions import (
    DEFAULT_POLICIES,
    TOOL_CATEGORIES,
    TOOL_OVERRIDES,
    READ,
    INTERACT,
    MODIFY,
    HIGH_RISK,
    DESTRUCTIVE,
    SYSTEM_CRITICAL,
    FINANCIAL,
    SENSITIVE,
    ALL_CATEGORIES,
    apply_arg_policies,
)


class ToolError(Exception):
    """Raised by a tool handler to signal a clean, user-facing failure."""

    def __init__(
        self,
        message: str,
        *,
        fatal: bool = False,
        category: str = "tool_failure",
        code: str | None = None,
        retryable: bool | None = None,
        severity: str = "error",
        details: dict | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.fatal = fatal
        self.category = category
        self.code = code or category
        self.retryable = retryable
        self.severity = severity
        self.details = details or {}

    def to_myraa_error(self, *, tool: str = "", request_id: str | None = None,
                       task_id: str | None = None, component: str = "desktop_agent") -> "MYRAAError":
        """Convert this tool error into the canonical MYRAAError (F6)."""
        from .brain.error_taxonomy import ErrorCategory, MYRAAError

        category = getattr(ErrorCategory, self.category.upper(), None)
        if category is None or not isinstance(category, ErrorCategory):
            category = ErrorCategory.TOOL_FAILURE
        return MYRAAError(
            category=category,
            message=self.message,
            details=dict(self.details),
            recoverable=bool(self.retryable),
            retryable=self.retryable,
            request_id=request_id,
            task_id=task_id,
            component=component,
            code=self.code,
            tool=tool or None,
            metadata={},
        )


class State:
    """Process-wide shared state for tool handlers."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        # Confirmation tokens for dangerous (power) actions.
        # token -> {"action": <tool_name>, "expires": <epoch>}
        self.confirmations: Dict[str, Dict[str, Any]] = {}
        # Browser singletons are not used — tools use the OS default browser.
        # The ONE vision-based automation engine (UniversalController) is shared
        # here so browser/desktop tool handlers can consume it. It is created
        # once in ApplicationContainer and executes through the registry
        # dispatcher, so every action it performs passes PermissionManager.
        self.universal_controller: Any = None


class StructuredLogger:
    def __init__(self, name: str):
        import logging
        self.log = logging.getLogger(name)

    def info(self, event: str, **kwargs):
        import json
        self.log.info(json.dumps({"event": event, "level": "INFO", **kwargs}))

    def error(self, event: str, error: Exception, **kwargs):
        import json
        self.log.error(json.dumps({"event": event, "level": "ERROR", "error": str(error), **kwargs}))

    def warning(self, event: str, **kwargs):
        import json
        self.log.warning(json.dumps({"event": event, "level": "WARNING", **kwargs}))

slog = StructuredLogger("myraa.desktop.core")

# Global dispatcher for unified tool execution (Phase 6)
# Set this before calling load_all() to enable unified execution for all tools
_UNIFIED_DISPATCHER: Any = None

# Dispatcher identity under which the tool modules were last registered.
# load_all() reloads the modules when this changes so registration is
# deterministic regardless of import order.
_last_loaded_dispatcher: Any = None


def set_unified_dispatcher(dispatcher: Any) -> None:
    """Set the global dispatcher for unified tool execution.

    Call this before load_all() to ensure all tools are registered with
    unified execution logic (validation, permissions, confirmation, etc.).
    """
    global _UNIFIED_DISPATCHER
    _UNIFIED_DISPATCHER = dispatcher

class ValidationLayer:
    @staticmethod
    def validate(args: Dict[str, Any], schema: Any, tool_name: str = "") -> Dict[str, Any]:
        if not isinstance(args, dict):
            raise ToolError(f"Validation failed: arguments must be an object, got {type(args).__name__}.")

        if schema is not None:
            try:
                return schema(**args).model_dump()
            except Exception as e:
                # Try fallback to .dict() for older pydantic versions
                try:
                    return schema(**args).dict()
                except Exception:
                    raise ToolError(f"Validation failed: {e}")

        # Lightweight structured tool-call schema (F4): enforce required args
        # centrally so a malformed model tool call is rejected before any handler.
        from .config.permissions import TOOL_REQUIRED_ARGS, OR_REQUIRED_ARGS

        required = TOOL_REQUIRED_ARGS.get(tool_name)
        if required:
            present = {k: v for k, v in args.items() if v is not None and str(v).strip() != ""}
            if tool_name in OR_REQUIRED_ARGS:
                # Alternatives: at least one listed arg must be present.
                if not any(name in present for name in OR_REQUIRED_ARGS[tool_name]):
                    raise ToolError(
                        f"Validation failed: '{tool_name}' requires one of: {', '.join(OR_REQUIRED_ARGS[tool_name])}."
                    )
            else:
                missing = [name for name in required if name not in present]
                if missing:
                    raise ToolError(
                        f"Validation failed: missing required argument(s) for '{tool_name}': {', '.join(missing)}."
                    )
        return args

from dataclasses import dataclass

@dataclass
class PermissionDecision:
    allowed: bool
    decision: str  # "allow", "deny", "confirm"
    tool: str
    category: str
    reason: str

class PermissionManager:
    CONFIRMATION_TTL_SECONDS = 60.0
    _lock = threading.Lock()  # Phase 8: thread-safe confirmation access

    @staticmethod
    def check(tool_name: str, args: Dict[str, Any]):
        # Determine category
        category = TOOL_CATEGORIES.get(tool_name)
        if category is None:
            # If not found, treat as high risk for safety
            category = HIGH_RISK

        # Determine policy: override > default
        policy = TOOL_OVERRIDES.get(tool_name)
        if policy is None:
            policy = DEFAULT_POLICIES.get(category)
        if policy is None:
            # Fallback to deny if something is misconfigured
            policy = "deny"

        # Arg-aware rules (path traversal, protected files, risky ops) can
        # escalate the category policy to deny or confirm.
        arg_override, arg_reason = apply_arg_policies(tool_name, args)
        reason = f"Tool '{tool_name}' is categorized as {category} with policy '{policy}'."
        if arg_override is not None:
            policy = arg_override
            reason = arg_reason or reason

        # Map policy to decision
        allowed = policy == "allow"
        decision = policy  # "allow", "deny", "confirm"

        perm_decision = PermissionDecision(
            allowed=allowed,
            decision=decision,
            tool=tool_name,
            category=category,
            reason=reason,
        )

        # Audit logging (best-effort)
        try:
            slog.info(
                "permission_decision",
                tool=tool_name,
                category=category,
                decision=decision,
                reason=reason,
            )
        except Exception:
            # Logging should never cause permission failure
            pass

        return perm_decision

    @staticmethod
    def mint_confirmation(tool_name: str, args: Dict[str, Any]) -> str:
        """Mint a single-use, short-lived token that authorizes one execution.

        Bound to the tool name (never re-playable for a different tool) and to
        the exact args, so confirming a modified request requires a fresh token.
        Thread-safe: uses a lock to prevent double-minting under concurrency.
        """
        import json
        import secrets
        import time

        with PermissionManager._lock:
            PermissionManager._purge_expired()
            token = secrets.token_urlsafe(6)
            STATE.confirmations[token] = {
                "tool": tool_name,
                "args_fingerprint": PermissionManager._fingerprint(args),
                "expires": time.time() + PermissionManager.CONFIRMATION_TTL_SECONDS,
            }
            return token

    @staticmethod
    def validate_confirmation(tool_name: str, args: Dict[str, Any], token: str | None) -> bool:
        """Validate + consume a confirmation token for ``tool_name``+``args``.
        Thread-safe: uses a lock to prevent double-consumption under concurrency.
        """
        import time

        with PermissionManager._lock:
            PermissionManager._purge_expired()
            if not token:
                return False
            entry = STATE.confirmations.pop(token, None)
            if entry is None:
                return False
            if entry.get("tool") != tool_name:
                return False
            if entry.get("args_fingerprint") != PermissionManager._fingerprint(args):
                return False
            return True

    @staticmethod
    def _purge_expired() -> None:
        import time

        now = time.time()
        expired = [t for t, v in STATE.confirmations.items() if v.get("expires", 0) < now]
        for t in expired:
            STATE.confirmations.pop(t, None)

    @staticmethod
    def _fingerprint(args: Dict[str, Any]) -> str:
        import hashlib
        import json

        try:
            payload = json.dumps(args, sort_keys=True, default=str)
        except Exception:
            payload = repr(sorted(args.items()))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

class RecoveryManager:
    @staticmethod
    def handle_failure(tool_name: str, exception: Exception, state: State) -> str:
        slog.error("tool_failure", exception, tool=tool_name)
        # F7: record into the authoritative recovery engine (containment
        # health + canonical retry classification). Best-effort, never raises.
        try:
            from .brain.failure_containment import recovery_engine
            recovery_engine.record_failure(tool_name, exception)
            return recovery_engine.tool_recovery_strategy(tool_name, exception)
        except Exception:
            return "abort"

class ResponseFormatter:
    @staticmethod
    def success(tool: str, result: Any, duration_ms: float) -> Dict[str, Any]:
        return {"ok": True, "tool": tool, "result": result, "meta": {"duration_ms": duration_ms}}

    @staticmethod
    def error(tool: str, error: str, duration_ms: float,
              error_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        meta = {"duration_ms": duration_ms}
        if error_info:
            meta["error"] = error_info
        return {"ok": False, "tool": tool, "error": error, "meta": meta}


STATE = State()

# tool_name -> handler(args: dict) -> dict
TOOLS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}
TOOL_SCHEMAS: Dict[str, Any] = {}

def register(name: str, schema: Any = None, dispatcher: Any = None):
    """Decorator to register a handler under a tool name.

    If dispatcher is provided, the handler will be wrapped with unified execution logic
    (validation, permissions, confirmation, error handling) to ensure all tool execution
    goes through the same unified system.
    If dispatcher is None, the global _UNIFIED_DISPATCHER will be used if set.
    """

    def deco(fn: Callable[[Dict[str, Any]], Dict[str, Any]]):
        # Use the provided dispatcher, or fall back to the global unified dispatcher
        effective_dispatcher = dispatcher if dispatcher is not None else _UNIFIED_DISPATCHER
        if effective_dispatcher is not None:
            # Wrap the handler with unified execution logic
            def unified_handler(args: Dict[str, Any]) -> Dict[str, Any]:
                import time
                from .brain.error_taxonomy import MYRAAError, classify_exception

                start_time = time.time()
                tool_name = name

                def _with_req_id(fmt: Dict[str, Any]) -> Dict[str, Any]:
                    fmt["meta"] = dict(fmt.get("meta") or {})
                    # Note: In the unified execution path via tools, we don't have
                    # request_id/task_id from HTTP requests, but we can add them if available
                    # through dispatcher context or other means. For now, we'll leave them out
                    # to maintain compatibility, but the structure is ready.
                    return fmt

                def _error_info(err: "MYRAAError") -> Dict[str, Any]:
                    """Attach a canonical F6 error payload."""
                    canonical = err.with_correlation(
                        component="desktop_agent",
                        tool=tool_name,
                    ).to_dict()
                    # F7: attach the ONE authoritative recovery decision.
                    try:
                        from .brain.failure_containment import recovery_engine
                        decision = recovery_engine.should_retry(err, 0, tool=tool_name)
                        canonical["retry"] = {
                            "action": decision.action.value,
                            "delay_seconds": round(decision.delay_seconds, 3),
                            "attempts_remaining": decision.attempts_remaining,
                            "reason": decision.reason,
                        }
                    except Exception:
                        pass
                    return canonical

                if tool_name not in TOOLS:
                    # This shouldn't happen since we're registering the tool, but just in case
                    known = ", ".join(sorted(TOOLS.keys()))
                    duration = (time.time() - start_time) * 1000
                    fmt = ResponseFormatter.error(tool_name, f"Unknown tool '{tool_name}'. Known tools: {known}", duration)
                    err = _error_info(
                        MYRAAError.invalid_request(
                            f"Unknown tool '{tool_name}'",
                            details={"known_tools": known},
                        )
                    )
                    fmt = ResponseFormatter.error(tool_name, fmt["error"], duration, error_info=err)
                    return fmt

                schema_local = TOOL_SCHEMAS.get(tool_name)

                # The confirmation token is transport metadata, never a tool argument.
                raw_args = dict(args or {})
                confirmation_token = raw_args.pop("confirmation_token", None) if isinstance(raw_args, dict) else None

                try:
                    # 1. Validation
                    valid_args = ValidationLayer.validate(raw_args, schema_local, tool_name=tool_name)
                    # 2. Permissions
                    perm_decision = PermissionManager.check(tool_name, valid_args)
                    if not perm_decision.allowed:
                        if perm_decision.decision == "deny":
                            # Permission denied: return error
                            duration = (time.time() - start_time) * 1000
                            err = _error_info(
                                MYRAAError.permission_denied(
                                    f"Permission denied: {perm_decision.reason}",
                                    tool=tool_name,
                                    details={"category": perm_decision.category},
                                )
                            )
                            fmt = ResponseFormatter.error(
                                tool_name, f"Permission denied: {perm_decision.reason}", duration, error_info=err
                            )
                            return fmt
                        elif perm_decision.decision == "confirm":
                            # Confirmation required. A valid single-use token unlocks the
                            # execution; otherwise mint one and hand it back so the caller
                            # can ask the user and re-invoke with confirmation_token.
                            if isinstance(confirmation_token, str) and PermissionManager.validate_confirmation(
                                tool_name, valid_args, confirmation_token
                            ):
                                # token accepted -> proceed to execution below
                                pass
                            else:
                                token = PermissionManager.mint_confirmation(tool_name, valid_args)
                                confirmation_data = {
                                    "requires_confirmation": True,
                                    "token": token,
                                    "reason": perm_decision.reason,
                                    "tool": tool_name,
                                    "category": perm_decision.category,
                                    "result": (
                                        f"Action '{tool_name}' requires your explicit confirmation. "
                                        f"Ask the user out loud to confirm, then call {tool_name} again "
                                        f"with the same arguments plus confirmation_token='{token}'. "
                                        f"The token is single-use and expires in 60 seconds."
                                    ),
                                }
                                duration = (time.time() - start_time) * 1000
                                err = _error_info(
                                    MYRAAError.confirmation_required(
                                        f"Action '{tool_name}' requires explicit user confirmation",
                                        tool=tool_name,
                                        details={"category": perm_decision.category},
                                    )
                                )
                                fmt = ResponseFormatter.success(tool_name, confirmation_data, duration)
                                fmt["meta"]["error"] = err
                                fmt["meta"]["requires_confirmation"] = True
                                return fmt
                        else:
                            # Unknown decision: fail closed
                            duration = (time.time() - start_time) * 1000
                            err = _error_info(
                                MYRAAError.internal_error(
                                    f"Unknown permission decision: {perm_decision.decision}",
                                    details={"decision": perm_decision.decision},
                                )
                            )
                            fmt = ResponseFormatter.error(
                                tool_name, f"Unknown permission decision: {perm_decision.decision}", duration, error_info=err
                            )
                            return fmt
                    # 3. Execution (only if allowed)
                    out = fn(valid_args)

                    result_text = str(out.get("result", out)) if isinstance(out, dict) else str(out)

                    duration = (time.time() - start_time) * 1000
                    fmt = ResponseFormatter.success(tool_name, out, duration)
                    return fmt

                except ToolError as e:
                    # Convert ToolError to standardized response
                    duration = (time.time() - start_time) * 1000
                    err = _error_info(e.to_myraa_error(tool=tool_name))
                    fmt = ResponseFormatter.error(tool_name, e.message, duration, error_info=err)
                    return fmt

                except Exception as e:
                    # Handle unexpected errors
                    duration = (time.time() - start_time) * 1000
                    err = _error_info(
                        classify_exception(e, tool=tool_name).with_correlation(
                            component="desktop_agent",
                            tool=tool_name,
                        )
                    )
                    fmt = ResponseFormatter.error(tool_name, f"Internal error in {tool_name}: {e}", duration, error_info=err)
                    return fmt

            # Keep a reference to the RAW handler so the canonical dispatcher
            # (CommandDispatcher) can execute it after ITS authoritative
            # permission gate. Without this, a dispatch through main.py runs
            # the gate TWICE (dispatcher + wrapper), and the second gate no
            # longer sees the popped confirmation_token — breaking the
            # confirm-handshake for every confirm-category tool (U.1 fix:
            # ONE permission authority per execution path).
            unified_handler.__raw_handler__ = fn
            unified_handler.__tool_name__ = name
            TOOLS[name] = unified_handler
        else:
            # Original behavior - direct registration (for backward compatibility/testing)
            TOOLS[name] = fn
        TOOL_SCHEMAS[name] = schema
        return fn

    return deco


# The set of all tool names MYRAA may route to this agent.
# Kept in sync with the functionDeclarations added in server.ts.
DESKTOP_TOOL_NAMES = [
    # applications / websites / search
    "openApplication",
    "closeApplication",
    "openWebsite",
    "searchWeb",
    "searchYouTube",
    "searchGoogle",
    "searchGitHub",
    # files
    "createFile",
    "readFile",
    "renameFile",
    "deleteFile",
    "moveFile",
    "openFolder",
    "listFiles",
    "searchFiles",
    # pc control (volume + gated power)
    "volumeUp",
    "volumeDown",
    "muteToggle",
    "setVolume",
    "requestPowerAction",  # first step: issues a confirmation token
    "executePowerAction",  # second step: runs the gated action
    # windows
    "minimizeWindow",
    "maximizeWindow",
    "activateWindow",
    "restoreWindow",
    "closeWindow",
    "switchApplication",
    # clipboard
    "copySelected",
    "pasteClipboard",
    "getClipboard",
    "clearClipboard",
    # screenshot / screen reading
    "takeScreenshot",
    "saveScreenshot",
    "analyzeScreenshot",
    "readScreen",
    # default-browser website tools (open/search; no browser engine is owned)
    "desktopBrowserOpen",
    "desktopBrowserNavigate",
    "desktopBrowserOpenTab",
    "desktopBrowserCloseTab",
    "desktopBrowserSearch",
    "desktopBrowserClick",
    "desktopBrowserType",
    "desktopBrowserFillForm",
    "desktopBrowserGoBack",
    "desktopBrowserGoForward",
    "desktopBrowserScroll",
    # coding assistance
    "createPythonFile",
    "runPythonScript",
    "createProjectFolder",
    "writeCodeFile",
    # system information
    "systemInfo",
    "gpuInfo",
    "temperatureInfo",
    # brightness control (V2)
    "brightnessUp",
    "brightnessDown",
    "setBrightness",
    # Windows auto-start management (V2)
    "enableAutoStart",
    "disableAutoStart",
    "getAutoStartStatus",
    # keyboard
    "typeText",
    "pressKey",
    "keyDown",
    "keyUp",
    "hotkey", 
    # mouse
    "moveMouse",
    "leftClick",
    "rightClick",
    "doubleClick",
    "middleClick",
    "dragMouse",
    "scrollMouse",
    "mousePosition",  
    # terminal
    "runShellCommand",
    "runCommand",
    # git
    "gitStatus",
    "gitDiff",
    "gitLog",
    "gitAdd",
    "gitCommit",
    "gitPush",
    "gitPull",
    "gitBranch",
    "gitCheckout",
]


# --- Eagerly import all tool modules so their @register decorators run. ---
# Each module is imported defensively: a hard import failure here would make
# the whole agent unstartable, which we want to avoid. The modules themselves
# keep optional-dependency imports lazy/try-except.
_MODULE_NAMES = [
    "tools_confirmation",
    "tools_applications",
    "tools_websites",
    "tools_search",
    "tools_files",
    "tools_pc",
    "tools_windows",
    "tools_clipboard",
    "tools_screenshot",
    "tools_browser",
    "tools_coding",
    "tools_system",
    "tools_startup",
    "tools_keyboard",
    "tools_mouse",
    "tools_terminal",
    "tools_git",
]


def load_all() -> None:
    # Deterministic registration: `importlib.import_module` caches modules, so if
    # any module was imported while _UNIFIED_DISPATCHER was None (e.g. a test or
    # a startup path that imports a tools_* module first), a later
    # set_unified_dispatcher(...)+load_all() would be a silent no-op and every
    # tool would stay UNWRAPPED — bypassing validation/permission/confirm gates
    # in registry.dispatch(). Track the dispatcher state we last loaded under and
    # force re-registration (reload) whenever it changes.
    global _last_loaded_dispatcher
    force = _last_loaded_dispatcher is not _UNIFIED_DISPATCHER
    for mod_name in _MODULE_NAMES:
        full = f"desktop_agent.{mod_name}"
        if force and full in sys.modules:
            importlib.reload(sys.modules[full])
        else:
            importlib.import_module(full, package="desktop_agent")
    _last_loaded_dispatcher = _UNIFIED_DISPATCHER


def dispatch(tool_name: str, args: Dict[str, Any]) -> Any:
    """Dispatch a tool call directly through the registry.

    This function provides a direct way to execute a tool by name,
    bypassing the HTTP endpoint and CommandDispatcher.

    Args:
        tool_name: The name of the tool to execute
        args: The arguments to pass to the tool

    Returns:
        The result of the tool execution

    Raises:
        ToolError: If the tool is not found or execution fails
    """
    if tool_name not in TOOLS:
        known = ", ".join(sorted(TOOLS.keys()))
        raise ToolError(f"Unknown tool '{tool_name}'. Known tools: {known}")

    handler = TOOLS[tool_name]
    return handler(args)


__all__ = ["TOOLS", "STATE", "DESKTOP_TOOL_NAMES", "ToolError", "register", "load_all", "dispatch"]
