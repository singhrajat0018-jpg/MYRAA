"""
MYRAA Desktop Control Agent — FastAPI entrypoint.

Single dispatch endpoint POST /execute { tool, args } -> { result } | { error }.
MYRAA's Node bridge (server.ts) calls this over HTTP on 127.0.0.1:8765.

Run:
    uvicorn desktop_agent.main:app --host 127.0.0.1 --port 8765
or:
    python -m desktop_agent.main
"""


from __future__ import annotations

import asyncio
from dataclasses import asdict

import json
import logging
import os
import time
from datetime import datetime
import traceback
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import __version__
from .registry import DESKTOP_TOOL_NAMES, TOOLS, ToolError, load_all
from .brain.error_taxonomy import MYRAAError, classify_exception

# Lazy imports for type hints only
if TYPE_CHECKING:
    from .brain.brain import Brain
    from .brain.models import BrainContext
    from desktop_agent.core.application_container import ApplicationContainer
    from .brain.execution_brain import ExecutionBrain
    from desktop_agent.brain.observer.manager import ObserverManager




logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("myraa.desktop")


_PROCESS_START = time.time()


# Load all tool modules so their handlers register before the app starts.
# Set the unified dispatcher for Phase 6: Unified Tool Execution
from .registry import set_unified_dispatcher
set_unified_dispatcher(True)  # Enable unified execution for all tools
load_all()
log.info("Loaded %d desktop tools: %s", len(TOOLS), ", ".join(sorted(TOOLS)))

# ==========================================================
# Global singletons — initialized to None, built during lifespan startup
# ==========================================================
container = None
execution_brain = None
BRAIN = None
observer_manager = None
dispatcher = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global container, execution_brain, BRAIN, observer_manager, dispatcher

    import asyncio
    startup_start = time.time()

    def log_step(step_num, step_name, start_time=None):
        if start_time is None:
            log.info(f"[STARTUP] {step_num:02d} BEGIN {step_name}")
            return time.time()
        else:
            duration = time.time() - start_time
            log.info(f"[STARTUP] {step_num:02d} END   {step_name} ({duration:.3f}s)")

    log.info("=" * 60)
    log.info("MYRAA Desktop Control Agent v%s starting.", __version__)
    log.info("=" * 60)

    # ==========================================================
    # Lazy imports - only import heavy modules during startup
    # ==========================================================
    t = log_step(1, "lazy imports")
    from .brain.brain import Brain
    from desktop_agent.core.application_container import ApplicationContainer
    from desktop_agent.brain.observer.registry import ObserverRegistry
    from desktop_agent.brain.observer.manager import ObserverManager
    from desktop_agent.brain.observer.observers.stock_observer import StockObserver
    from desktop_agent.brain.observer.observers.screen_observer import ScreenObserver
    from desktop_agent.desktop.vision.screenshot_engine import ScreenshotEngine
    from desktop_agent.desktop.vision.frame_difference import FrameDifference
    from desktop_agent.desktop.vision.ocr_engine import OCREngine
    from desktop_agent.desktop.vision.ocr_backends.tesseract_backend import TesseractBackend as TesseractOCR
    from desktop_agent.finance.finance_service import FinanceService
    from desktop_agent.finance.market.provider_manager import ProviderManager
    from desktop_agent.finance.market.providers.yahoo_provider import YahooProvider
    from desktop_agent.finance.portfolio.portfolio_manager import PortfolioManager
    log_step(1, "lazy imports", t)

    # ==========================================================
    # Initialize core services with timeout
    # ==========================================================
    try:
        t = log_step(2, "create CommandDispatcher")
        dispatcher = CommandDispatcher()
        log_step(2, "create CommandDispatcher", t)

        t = log_step(3, "create ApplicationContainer")
        async with asyncio.timeout(30):
            container = ApplicationContainer(dispatcher=dispatcher)
        log_step(3, "create ApplicationContainer", t)

        t = log_step(4, "get execution_brain from container")
        execution_brain = container.execution_brain
        log_step(4, "get execution_brain from container", t)

        t = log_step(5, "create Brain")
        BRAIN = Brain(
            dispatcher,
            brain_engine=container.brain_engine,
            orchestrator=container.orchestrator,
        )
        log_step(5, "create Brain", t)

        t = log_step(6, "register execution events")
        BRAIN.brain_engine.register_execution_events()
        log_step(6, "register execution events", t)

    except asyncio.TimeoutError:
        log.error("[STARTUP] TIMEOUT during ApplicationContainer/Brain initialization")
        log.error("[STARTUP] Startup hung - check ApplicationContainer._build() for blocking operations")
        raise
    except Exception as e:
        log.error(f"[STARTUP] FAILED during core initialization: {e}")
        import traceback
        traceback.print_exc()
        raise

    # ==========================================================
    # Observer Bootstrap with timeout
    # ==========================================================
    try:
        t = log_step(7, "create PortfolioManager")
        portfolio = PortfolioManager()
        log_step(7, "create PortfolioManager", t)

        t = log_step(8, "create ProviderManager")
        provider = ProviderManager()
        log_step(8, "create ProviderManager", t)

        t = log_step(9, "register YahooProvider")
        provider.register("yahoo", YahooProvider())
        provider.use("yahoo")
        log_step(9, "register YahooProvider", t)

        t = log_step(10, "create FinanceService")
        finance_service = FinanceService(portfolio=portfolio, provider=provider)
        log_step(10, "create FinanceService", t)

        # Initialize screen capture components
        t = log_step(11, "initialize screen capture components")
        screenshot_engine = ScreenshotEngine()
        frame_difference = FrameDifference()
        ocr_engine = OCREngine(TesseractOCR())
        log_step(11, "initialize screen capture components", t)

        t = log_step(12, "create ObserverRegistry")
        registry = ObserverRegistry()
        log_step(12, "create ObserverRegistry", t)

        t = log_step(13, "register stock_observer")
        registry.register("stock_observer", StockObserver(finance_service))
        log_step(13, "register stock_observer", t)

        t = log_step(14, "register screen_observer")
        screen_obs = ScreenObserver(
            name="screen_observer",
            process_fps=4,
            change_threshold=0.02,
            ocr_interval=5.0,
            screen_share=container.screen_share,
        )
        registry.register("screen_observer", screen_obs)
        log_step(14, "register screen_observer", t)

        t = log_step(15, "create ObserverManager")
        observer_manager = ObserverManager(
            registry=registry,
            event_handler=BRAIN.brain_engine.process_event,
            poll_interval=5,
        )
        log_step(15, "create ObserverManager", t)

    except asyncio.TimeoutError:
        log.error("[STARTUP] TIMEOUT during Observer Bootstrap")
        raise
    except Exception as e:
        log.error(f"[STARTUP] FAILED during Observer Bootstrap: {e}")
        import traceback
        traceback.print_exc()
        raise

    # ==========================================================
    # Start background services - DO NOT BLOCK
    # ==========================================================
    try:
        t = log_step(16, "start screen share engine")
        try:
            container.screen_share.start()
            container.screen_share.wait_for_first_frame(timeout=5.0)
            log_step(16, "start screen share engine", t)
        except Exception as exc:
            log.warning("[STARTUP] ScreenShareEngine failed to start: %s", exc)

        t = log_step(16, "start continuous vision controller")
        try:
            container.continuous_vision.start()
            log_step(16, "start continuous vision controller", t)
        except Exception as exc:
            log.warning("[STARTUP] ContinuousVisionController failed to start: %s", exc)

        t = log_step(17, "start autonomous runtime")
        container.runtime.start()
        log_step(17, "start autonomous runtime", t)

        t = log_step(18, "start observers")
        observer_manager.start()
        log_step(18, "start observers", t)

    except Exception as e:
        log.error(f"[STARTUP] FAILED during background services: {e}")
        import traceback
        traceback.print_exc()
        raise

    startup_duration = time.time() - startup_start
    log.info("=" * 60)
    log.info(f"[STARTUP] COMPLETE - Desktop Agent READY in {startup_duration:.2f}s")
    log.info("=" * 60)

    try:
        yield

    finally:
        log.info("[SHUTDOWN] Stopping Desktop Agent...")

        t = log_step(99, "stop continuous vision")
        try:
            container.continuous_vision.stop()
        except Exception as e:
            log.warning("[SHUTDOWN] ContinuousVisionController stop error: %s", e)
        log_step(99, "stop continuous vision", t)

        t = log_step(97, "stop screen share")
        try:
            container.screen_share.stop()
        except Exception as e:
            log.warning("[SHUTDOWN] ScreenShareEngine stop error: %s", e)
        log_step(97, "stop screen share", t)

        t = log_step(96, "stop vision pipeline")
        try:
            container.vision.stop()
        except Exception as e:
            log.warning("[SHUTDOWN] Vision pipeline stop error: %s", e)
        log_step(96, "stop vision pipeline", t)

        t = log_step(95, "stop runtime")
        container.runtime.stop()
        log_step(95, "stop runtime", t)

        t = log_step(94, "stop observers")
        observer_manager.stop()
        log_step(94, "stop observers", t)

        t = log_step(93, "shutdown browser")
        try:
            from .tools_browser import shutdown_browser
            shutdown_browser()
        except Exception as e:
            log.warning("[SHUTDOWN] Browser shutdown error: %s", e)
        log_step(95, "shutdown browser", t)

        log.info("[SHUTDOWN] MYRAA stopped cleanly.")



app = FastAPI(
    title="MYRAA Desktop Control Agent",
    version=__version__,
    description="JARVIS-style desktop automation backend for MYRAA.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ExecuteRequest(BaseModel):
    tool: str
    args: Dict[str, Any] = {}
    request_id: Optional[str] = None
    task_id: Optional[str] = None

class BrainRequest(BaseModel):
    text: str
    context: Dict[str, Any] = {}
    request_id: Optional[str] = None
    task_id: Optional[str] = None
    source: Optional[str] = None


class ExecuteResponse(BaseModel):
    ok: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    tool: str = ""
    meta: Dict[str, Any] = {}


class BrainResponse(BaseModel):
    ok: bool
    result: Optional[Any] = None
    error: Optional[str] = None


class HealthMonitor:
    @staticmethod
    def get_stats() -> Dict[str, Any]:
        # /health is a DETAILED report, not a gate. It must never 500:
        # any internal failure degrades the payload instead of killing the
        # endpoint (a 500 here used to make the launcher and the Node boot
        # probe falsely report the whole agent as dead).
        try:
            return HealthMonitor._collect_stats()
        except Exception as e:
            log.warning(f"/health aggregation failed: {e}")
            try:
                return {
                    "status": "degraded",
                    "name": "MYRAA Desktop Control Agent",
                    "version": __version__,
                    "tool_count": len(TOOLS),
                    "error": f"health aggregation failed: {e}",
                }
            except Exception:
                return {
                    "status": "degraded",
                    "name": "MYRAA Desktop Control Agent",
                    "error": f"health aggregation failed: {e}",
                }

    @staticmethod
    def _collect_stats() -> Dict[str, Any]:
        stats = {
            "status": "ok",
            "name": "MYRAA Desktop Control Agent",
            "version": __version__,
            "tools": sorted(TOOLS.keys()),
            "tool_count": len(TOOLS),
            "system": {}
        }
        try:
            import psutil
            stats["system"] = {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "ram_percent": psutil.virtual_memory().percent,
                "disk_usage_percent": psutil.disk_usage('/').percent
            }
        except Exception as e:
            stats["system"] = {"error": str(e)}

        # Add subsystem health from failure containment manager
        try:
            from .brain.failure_containment import failure_containment_manager
            key_subsystems = ['vision', 'target_resolution', 'action_execution', 'browser', 'finance', 'perception']
            subsystem_health = {}
            for subsystem in key_subsystems:
                subsystem_health[subsystem] = failure_containment_manager.get_health(subsystem)
            stats["subsystems"] = subsystem_health
        except Exception as e:
            log.warning(f"Failed to get subsystem health: {e}")
            stats["subsystems"] = {"status": "unavailable", "error": str(e)}

        return stats

@app.get("/system/metrics")
def system_metrics():
    """Real-time system metrics for the frontend dashboard."""
    import psutil
    result = {
        "cpu": 0.0,
        "ram": 0.0,
        "gpu": None,
        "gpu_name": None,
        "vram_used": None,
        "vram_total": None,
        "gpu_temp": None,
        "npu": None,
        "network_down": 0.0,
        "network_up": 0.0,
        "storage_used": 0,
        "storage_total": 1,
        "power_percent": None,
        "power_ac": True,
    }
    try:
        result["cpu"] = round(psutil.cpu_percent(interval=0.1), 1)
        vm = psutil.virtual_memory()
        result["ram"] = round(vm.percent, 1)
        disk = psutil.disk_usage("/")
        result["storage_used"] = round(disk.used / (1024**3), 1)
        result["storage_total"] = round(disk.total / (1024**3), 1)
        # Network I/O
        net = psutil.net_io_counters()
        result["network_down"] = round(net.bytes_recv / (1024**2), 1)
        result["network_up"] = round(net.bytes_sent / (1024**2), 1)
        # Battery
        try:
            bat = psutil.sensors_battery()
            if bat:
                result["power_percent"] = bat.percent
                result["power_ac"] = bat.power_plugged
            else:
                result["power_percent"] = None
                result["power_ac"] = True
        except Exception:
            result["power_percent"] = None
            result["power_ac"] = True
    except Exception:
        pass

    # GPU via pynvml (NVIDIA)
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        result["gpu"] = util.gpu
        result["gpu_name"] = pynvml.nvmlDeviceGetName(handle)
        result["vram_used"] = round(mem.used / (1024**3), 2)
        result["vram_total"] = round(mem.total / (1024**3), 2)
        try:
            result["gpu_temp"] = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        except Exception:
            result["gpu_temp"] = None
        pynvml.nvmlShutdown()
    except Exception:
        result["gpu"] = None
        result["gpu_name"] = None

    # NPU — not typically exposed on consumer hardware
    result["npu"] = None

    return result

@app.get("/brain/debug/working-memory")
def working_memory():
    if BRAIN is None:
        return {"error": "Brain not initialized"}
    return asdict(
        BRAIN.brain_engine.working_snapshot()
    )

@app.get("/brain/debug/reflections")
def debug_reflections():
    if BRAIN is None:
        return {"error": "Brain not initialized"}

    print(id(BRAIN.brain_engine.reflection))

    print(BRAIN.brain_engine.reflection.recent())

    from dataclasses import asdict

    return [
        asdict(x)
        for x in BRAIN.brain_engine.reflection.recent()
    ]

@app.get("/brain/debug/last-route")
def last_route():
    """EPIC-07: explain the last Response Router decision (debug only)."""
    if BRAIN is None:
        return {"error": "Brain not initialized"}
    route = getattr(BRAIN.brain_engine, "_last_response_route", None)

    if route is None:
        return {"route": None}

    return route.to_dict()

@app.get("/brain/debug/last-research")
def last_research():
    """EPIC-08: last ResearchRouter outcome (debug only). No API keys exposed."""
    if BRAIN is None:
        return {"error": "Brain not initialized"}
    research = getattr(BRAIN.brain_engine, "_last_research_result", None)

    if research is None:
        return {"research": None}

    return research.to_dict()

@app.get("/health")
def health() -> Dict[str, Any]:
    return HealthMonitor.get_stats()


@app.get("/health/live")
def health_live() -> Dict[str, Any]:
    """F9 liveness probe: process is up. Never touches providers or disk."""
    return {
        "status": "ok",
        "name": "MYRAA Desktop Control Agent",
        "version": __version__,
        "uptime_seconds": round(time.time() - _PROCESS_START, 2),
    }


@app.get("/news")
def news_endpoint(q: str = "latest news", category: Optional[str] = None):
    """News search endpoint — fetches news via Tavily provider."""
    from .intelligence.news_provider import NewsProvider
    provider = NewsProvider()
    result = provider.fetch(query=q, category=category)
    return result.to_dict()


_PROVIDER_FACTORIES = {
    "ollama": lambda: OllamaProvider(),
}


def _build_provider_health() -> List[Dict[str, Any]]:
    """Provider readiness: configured / available / state / model. No secrets."""
    from .brain.ai.providers.ollama_provider import OllamaProvider
    from .brain.failure_containment import recovery_engine

    result: List[Dict[str, Any]] = []
    for name in ("ollama",):
        try:
            provider = _PROVIDER_FACTORIES[name]()
            available = bool(provider.available())
            state = recovery_engine.provider_state(name)
            result.append({
                "provider": name,
                "configured": available,
                "available": available,
                "model": getattr(provider, "model", ""),
                "state": state,
                "degraded": state in ("DEGRADED", "COOLDOWN"),
                "rate_limited": state == "COOLDOWN",
            })
        except Exception:
            result.append({
                "provider": name,
                "configured": False,
                "available": False,
                "model": "",
                "state": "UNAVAILABLE",
                "degraded": True,
                "rate_limited": False,
            })
    return result


def _node_reachable() -> bool:
    """Best-effort reverse probe of the Node side (does not block readiness)."""
    import urllib.request
    url = os.getenv("MYRAA_NODE_HEALTH_URL", "http://127.0.0.1:3000/api/agent-health")
    try:
        with urllib.request.urlopen(url, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _storage_writable() -> bool:
    """Check the memory/data directory is writable (best-effort)."""
    import tempfile
    data_dir = os.getenv("MYRAA_DATA_DIR") or os.getcwd()
    try:
        probe = os.path.join(data_dir, f".myraa_health_probe_{os.getpid()}.tmp")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except Exception:
        return False


@app.get("/health/ready")
def health_ready() -> Dict[str, Any]:
    """F9 readiness probe. Healthy only when all critical dependencies are up.

    Checks: Node reachability, Python agent, memory, AI providers, browser,
    tool dispatcher, storage. Never exposes API keys.
    """
    from .brain.failure_containment import failure_containment_manager
    from .brain.metrics import telemetry

    deps: Dict[str, Any] = {
        "python_agent": {"status": "HEALTHY", "detail": "alive"},
        "node": {"status": "HEALTHY" if _node_reachable() else "UNAVAILABLE"},
        "memory": {"status": "HEALTHY"},
        "ai_providers": {"status": "HEALTHY"},
        "browser": {"status": "HEALTHY"},
        "tool_dispatcher": {"status": "HEALTHY"},
        "storage": {"status": "HEALTHY" if _storage_writable() else "DEGRADED"},
    }

    # Memory-persistence health (Windows/OneDrive atomic-write layer).
    try:
        from .brain.memory import persistence as mem_persistence

        deps["memory"]["detail"] = mem_persistence.persistence_status()
        if deps["memory"]["detail"].get("status") == "DEGRADED":
            deps["memory"]["status"] = "DEGRADED"
    except Exception:  # noqa: BLE001
        pass

    try:
        import psutil
        if psutil.virtual_memory().percent > 95:
            deps["memory"]["status"] = "DEGRADED"
            deps["memory"]["detail"] = "system memory >95%"
    except Exception:
        deps["memory"]["status"] = "DEGRADED"
        deps["memory"]["detail"] = "psutil unavailable"

    browser_health = failure_containment_manager.get_health("browser")
    if browser_health != "HEALTHY":
        deps["browser"]["status"] = browser_health

    tool_count = len(TOOLS)
    if tool_count == 0:
        deps["tool_dispatcher"]["status"] = "UNAVAILABLE"
        deps["tool_dispatcher"]["detail"] = "no tools registered"
    else:
        deps["tool_dispatcher"]["detail"] = f"{tool_count} tools registered"

    provider_health = _build_provider_health()
    deps["ai_providers"]["detail"] = provider_health
    if not any(p["available"] for p in provider_health):
        deps["ai_providers"]["status"] = "UNAVAILABLE"
    elif any(p["degraded"] for p in provider_health):
        deps["ai_providers"]["status"] = "DEGRADED"

    status_counts = {}
    for d in deps.values():
        status_counts[d["status"]] = status_counts.get(d["status"], 0) + 1

    if status_counts.get("UNAVAILABLE", 0):
        overall = "UNAVAILABLE"
    elif status_counts.get("DEGRADED", 0):
        overall = "DEGRADED"
    else:
        overall = "HEALTHY"

    telemetry.record(
        component="health",
        route="/health/ready",
        status="ok" if overall == "HEALTHY" else "error",
    )

    return {
        "status": overall,
        "dependencies": deps,
        "tool_count": tool_count,
        "version": __version__,
        "uptime_seconds": round(time.time() - _PROCESS_START, 2),
    }


@app.get("/tools")
def list_tools() -> Dict[str, Any]:
    return {"tools": sorted(TOOLS.keys()), "count": len(TOOLS)}


class CommandDispatcher:
    @staticmethod
    def dispatch(req: ExecuteRequest) -> ExecuteResponse:
        import time as _t
        from .brain.metrics import telemetry
        start = _t.perf_counter()
        tool = getattr(req, "tool", "") or ""
        request_id = getattr(req, "request_id", None) or "-"
        task_id = getattr(req, "task_id", None)
        status = "ok"
        error_category = ""
        verification_status = ""
        resp = None
        telemetry.start_task(request_id, tool=tool)
        try:
            resp = CommandDispatcher._dispatch_inner(req)
            return resp
        finally:
            duration_ms = (_t.perf_counter() - start) * 1000
            meta = dict(getattr(resp, "meta", None) or {})
            if resp is None or not getattr(resp, "ok", False):
                status = "error"
                err = meta.get("error") or {}
                error_category = err.get("category", "") if isinstance(err, dict) else ""
            elif meta.get("requires_confirmation"):
                status = "confirmation"
            verif = meta.get("verification")
            verification_status = verif.get("status", "") if isinstance(verif, dict) else ""
            telemetry.record(
                request_id=request_id,
                task_id=task_id,
                component="desktop_agent",
                route="/execute",
                tool=tool,
                status=status,
                latency_ms=duration_ms,
                error_category=error_category or None,
                verification_status=verification_status or None,
            )
            telemetry.end_task(request_id)

    @staticmethod
    def _dispatch_inner(req: ExecuteRequest) -> ExecuteResponse:
        import time
        from .registry import ValidationLayer, PermissionManager, RecoveryManager, ResponseFormatter, TOOL_SCHEMAS, STATE
        start_time = time.time()
        tool = req.tool
        args = req.args or {}
        request_id = getattr(req, "request_id", None) or "-"
        task_id = getattr(req, "task_id", None)
        log.info("EXEC tool=%s args=%s request_id=%s", tool, _short_args(args), request_id)

        def _with_req_id(fmt: Dict[str, Any]) -> Dict[str, Any]:
            fmt["meta"] = dict(fmt.get("meta") or {})
            fmt["meta"]["request_id"] = request_id
            if task_id:
                fmt["meta"]["task_id"] = task_id
            return fmt

        def _error_info(err: "MYRAAError") -> Dict[str, Any]:
            """Attach a canonical F6 error payload (secrets never included)."""
            canonical = err.with_correlation(
                request_id=request_id,
                task_id=task_id,
                component="desktop_agent",
                tool=tool,
            ).to_dict()
            # F7: attach the ONE authoritative recovery decision.
            try:
                from .brain.failure_containment import recovery_engine
                decision = recovery_engine.should_retry(err, 0, tool=tool)
                canonical["retry"] = {
                    "action": decision.action.value,
                    "delay_seconds": round(decision.delay_seconds, 3),
                    "attempts_remaining": decision.attempts_remaining,
                    "reason": decision.reason,
                }
            except Exception:
                pass
            return canonical

        if tool not in TOOLS:
            known = ", ".join(sorted(TOOLS.keys()))
            duration = (time.time() - start_time) * 1000
            fmt = ResponseFormatter.error(tool, f"Unknown tool '{tool}'. Known tools: {known}", duration)
            err = _error_info(
                MYRAAError.invalid_request(
                    f"Unknown tool '{tool}'",
                    details={"known_tools": known},
                )
            )
            fmt = ResponseFormatter.error(tool, fmt["error"], duration, error_info=err)
            return ExecuteResponse(**_with_req_id(fmt))

        handler = TOOLS[tool]
        schema = TOOL_SCHEMAS.get(tool)

        # The confirmation token is transport metadata, never a tool argument.
        raw_args = dict(args or {})
        confirmation_token = raw_args.pop("confirmation_token", None) if isinstance(raw_args, dict) else None

        try:
            # 1. Validation
            valid_args = ValidationLayer.validate(raw_args, schema, tool_name=tool)
            # 2. Permissions
            perm_decision = PermissionManager.check(tool, valid_args)
            if not perm_decision.allowed:
                if perm_decision.decision == "deny":
                    # Permission denied: return error
                    duration = (time.time() - start_time) * 1000
                    err = _error_info(
                        MYRAAError.permission_denied(
                            f"Permission denied: {perm_decision.reason}",
                            tool=tool,
                            details={"category": perm_decision.category},
                        )
                    )
                    fmt = ResponseFormatter.error(
                        tool, f"Permission denied: {perm_decision.reason}", duration, error_info=err
                    )
                    return ExecuteResponse(**_with_req_id(fmt))
                elif perm_decision.decision == "confirm":
                    # Confirmation required. A valid single-use token unlocks the
                    # execution; otherwise mint one and hand it back so the caller
                    # can ask the user and re-invoke with confirmation_token.
                    if isinstance(confirmation_token, str) and PermissionManager.validate_confirmation(
                        tool, valid_args, confirmation_token
                    ):
                        # token accepted -> proceed to execution below
                        pass
                    else:
                        token = PermissionManager.mint_confirmation(tool, valid_args)
                        confirmation_data = {
                            "requires_confirmation": True,
                            "token": token,
                            "reason": perm_decision.reason,
                            "tool": tool,
                            "category": perm_decision.category,
                            "result": (
                                f"Action '{tool}' requires your explicit confirmation. "
                                f"Ask the user out loud to confirm, then call {tool} again "
                                f"with the same arguments plus confirmation_token='{token}'. "
                                f"The token is single-use and expires in 60 seconds."
                            ),
                        }
                        duration = (time.time() - start_time) * 1000
                        err = _error_info(
                            MYRAAError.confirmation_required(
                                f"Action '{tool}' requires explicit user confirmation",
                                tool=tool,
                                details={"category": perm_decision.category},
                            )
                        )
                        fmt = ResponseFormatter.success(tool, confirmation_data, duration)
                        fmt["meta"]["error"] = err
                        fmt["meta"]["requires_confirmation"] = True
                        return ExecuteResponse(**_with_req_id(fmt))
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
                        tool, f"Unknown permission decision: {perm_decision.decision}", duration, error_info=err
                    )
                    return ExecuteResponse(**_with_req_id(fmt))
            # 3. Execution (only if allowed)
            # U.1: execute the RAW handler. The dispatcher's gate above IS the
            # permission authority for this path; TOOLS[tool] may be the
            # unified wrapper (used by direct registry.dispatch callers),
            # which would otherwise re-run validation/permissions and lose
            # the popped confirmation_token.
            raw_handler = getattr(handler, "__raw_handler__", handler)
            out = raw_handler(valid_args)

            # Check if the handler already returned a standardized response
            # (has ok, tool, and meta keys) to avoid double-wrapping
            if isinstance(out, dict) and "ok" in out and "tool" in out and "meta" in out:
                # Handler already returned a standardized response, use it directly
                standardized_response = out
            else:
                # Handler returned raw result, wrap it in standardized format
                result_text = str(out.get("result", out)) if isinstance(out, dict) else str(out)
                log.info("DONE tool=%s -> %s request_id=%s", tool, result_text[:160], request_id)
                duration = (time.time() - start_time) * 1000
                standardized_response = ResponseFormatter.success(tool, out, duration)

            return ExecuteResponse(**_with_req_id(standardized_response))

        except ToolError as e:
            log.warning("ToolError in %s: %s request_id=%s", tool, e.message, request_id)
            RecoveryManager.handle_failure(tool, e, STATE)
            duration = (time.time() - start_time) * 1000
            err = _error_info(e.to_myraa_error(tool=tool, request_id=request_id, task_id=task_id))
            fmt = ResponseFormatter.error(tool, e.message, duration, error_info=err)
            return ExecuteResponse(**_with_req_id(fmt))
            
        except Exception as e:
            log.error("Unhandled error in %s: %s request_id=%s\n%s", tool, e, request_id, traceback.format_exc())
            RecoveryManager.handle_failure(tool, e, STATE)
            duration = (time.time() - start_time) * 1000
            err = _error_info(
                classify_exception(e, tool=tool).with_correlation(
                    request_id=request_id,
                    task_id=task_id,
                    component="desktop_agent",
                    tool=tool,
                )
            )
            fmt = ResponseFormatter.error(tool, f"Internal error in {tool}: {e}", duration, error_info=err)
            return ExecuteResponse(**_with_req_id(fmt))

@app.post("/execute")
def execute(req: ExecuteRequest):

    return execution_brain.execute(req)

@app.post("/brain", response_model=BrainResponse)
def brain(req: BrainRequest):
    """Phase U: canonical conversational entry.

    Delegates to THE AssistantRuntime (one request pipeline, one task_id,
    one lifecycle). Response schema is unchanged:
      ok=True  -> result {success, message, decision, capability, metadata}
      ok=False -> error + result.error (canonical F6 payload)

    U.1: works even when invoked in-process WITHOUT lifespan startup
    (tests call brain() directly with container=None) — a lazily-built
    standalone AssistantRuntime backs those calls.
    """
    from .brain.assistant_runtime import AssistantRequest, InputType

    areq = AssistantRequest(
        user_input=req.text,
        input_type=InputType.TEXT,
        request_id=getattr(req, "request_id", None),
        task_id=getattr(req, "task_id", None),
        source="api/brain",
        context=dict(req.context or {}),
    )
    resp = _assistant_runtime().handle(areq)

    # ok == result["success"] must hold for EVERY response. When the runtime
    # produced a full result envelope (success/message/decision/capability/
    # metadata), pass it through untouched; otherwise synthesize one so the
    # contract stays total.
    if resp.result is not None:
        return BrainResponse(ok=resp.ok, error=None if resp.ok else str(
            (resp.error or {}).get("message", "task failed")
        ), result=resp.result)

    return BrainResponse(
        ok=False,
        error=str((resp.error or {}).get("message", "task failed")),
        result={
            "success": False,
            "message": str((resp.error or {}).get("message", "")),
            "decision": resp.decision or "ERROR",
            "capability": resp.capability or "",
            "metadata": {
                "brain": "MYRAA",
                "version": "MCE v2",
                "route": resp.route or "ASSISTANT_RUNTIME",
                "request_id": resp.request_id,
                "task_id": resp.task_id,
                "error": resp.error,
            },
        },
    )


@app.post("/brain/stream")
def brain_stream(req: BrainRequest):
    """Intelligent streaming entry — FastCore routes, then streams response.

    FastCore classifies the intent, then dispatches to:
    - Weather provider → structured weather response
    - News provider → structured news response
    - Research router → web research + synthesis
    - Ollama streaming → conversation/reasoning/coding

    Returns a StreamingResponse with text/event-stream content type.
    Each event is a JSON line: {"type": "chunk", "text", "metadata", ...}.
    """
    import json as _json
    import time as _time

    def generate():
        request_start = _time.perf_counter()
        try:
            text = (req.text or "").strip()
            if not text:
                yield _json.dumps({"type": "error", "message": "Empty input"}) + "\n"
                yield _json.dumps({"type": "done", "text": ""}) + "\n"
                return

            # ── FastCore Classification ──────────────────────────────
            from .fastcore.classifier import FastCoreClassifier
            classifier = FastCoreClassifier()
            fc_start = _time.perf_counter()
            fc_output = classifier.classify(text)
            fc_latency_ms = (_time.perf_counter() - fc_start) * 1000

            log.info(
                "[Brain Stream] FastCore: task=%s complexity=%s model=%s confidence=%.2f (%.1fms)",
                fc_output.task_type.value, fc_output.complexity.value,
                fc_output.model_route.value, fc_output.confidence, fc_latency_ms,
            )

            # Emit classification metadata
            yield _json.dumps({
                "type": "metadata",
                "intent": fc_output.task_type.value,
                "complexity": fc_output.complexity.value,
                "model_route": fc_output.model_route.value,
                "confidence": round(fc_output.confidence, 3),
                "fastcore_latency_ms": round(fc_latency_ms, 2),
            }) + "\n"

            # ── Capability Engine Routing (Phase 19B) ────────────────
            # Try the CapabilityEngine for provider resolution when available.
            # Falls back to existing hard-coded routing if bridge is unavailable.
            _capability_routed = False
            try:
                from .capabilities.bridge import get_capability_bridge, get_capability_for_task
                _cap_id = get_capability_for_task(fc_output.task_type.value)
                if _cap_id:
                    _bridge = get_capability_bridge()
                    if _bridge.is_available():
                        _cap_result = _bridge.execute(_cap_id, {"query": text, "task_type": fc_output.task_type.value})
                        if _cap_result and _cap_result.get("success"):
                            _cap_data = _cap_result.get("data", {})
                            _cap_text = _cap_data.get("text") or _cap_data.get("response") or str(_cap_data)
                            _cap_provider = _cap_result.get("providerId", "unknown")
                            yield _json.dumps({"type": "chunk", "text": _cap_text}) + "\n"
                            yield _json.dumps({
                                "type": "done",
                                "text": _cap_text,
                                "provider": _cap_provider,
                                "capability": _cap_id,
                                "data": _cap_data,
                            }) + "\n"
                            _capability_routed = True
                            return
            except Exception as _cap_err:
                log.debug("[Brain Stream] Capability bridge unavailable: %s", _cap_err)

            # ── Weather (fallback) ───────────────────────────────────
            if fc_output.task_type.value == "weather_task":
                from .intelligence.weather_provider import WeatherProvider
                wp = WeatherProvider()
                city = wp.extract_city_from_query(text)
                weather = wp.fetch(city=city)
                response_text = weather.to_natural_response(lang="hi")
                yield _json.dumps({"type": "chunk", "text": response_text}) + "\n"
                yield _json.dumps({
                    "type": "done",
                    "text": response_text,
                    "provider": "open-meteo",
                    "data": weather.to_dict(),
                }) + "\n"
                return

            # ── News (fallback) ──────────────────────────────────────
            if fc_output.task_type.value == "news_task":
                from .intelligence.news_provider import NewsProvider
                np = NewsProvider()
                category = np._extract_category(text)
                result = np.fetch(query=text, category=category)
                response_text = result.to_natural_response()
                yield _json.dumps({"type": "chunk", "text": response_text}) + "\n"
                yield _json.dumps({
                    "type": "done",
                    "text": response_text,
                    "provider": "tavily",
                    "data": result.to_dict(),
                }) + "\n"
                return

            # ── Research (existing pipeline, fallback) ───────────────
            if fc_output.task_type.value in ("web_research", "current_information"):
                # Try the existing ResearchRouter if available
                try:
                    from .brain.research.research_router import ResearchRouter
                    from .brain.router.response_router import ResearchHandoff
                    rr = ResearchRouter()
                    handoff = ResearchHandoff(
                        query=text,
                        reason="FastCore classified as " + fc_output.task_type.value,
                        needs_synthesis=True,
                    )
                    research_result = rr.research(handoff)
                    if research_result and research_result.success and research_result.synthesized:
                        yield _json.dumps({"type": "chunk", "text": research_result.synthesized}) + "\n"
                        sources = [{"title": s.title, "url": s.url} for s in research_result.sources[:5]]
                        yield _json.dumps({
                            "type": "done",
                            "text": research_result.synthesized,
                            "provider": "research_router",
                            "sources": sources,
                        }) + "\n"
                        return
                except Exception as e:
                    log.info("[Brain Stream] ResearchRouter unavailable: %s, falling back to Ollama", e)

            # ── Ollama Streaming (conversation/reasoning/coding) ────
            # Get the Ollama provider from AIManager
            ai_mgr = None
            if container is not None and hasattr(container, "brain_engine"):
                ai_mgr = getattr(container.brain_engine, "ai", None)
            if ai_mgr is None:
                from .brain.ai.providers.ollama_provider import OllamaProvider
                provider = OllamaProvider()
            else:
                provider = ai_mgr.active_provider()

            if not provider or not provider.available():
                yield _json.dumps({"type": "error", "message": "Ollama is not available"}) + "\n"
                yield _json.dumps({"type": "done", "text": ""}) + "\n"
                return

            # Model selection based on FastCore routing + task type
            model = None
            task_type = fc_output.task_type.value
            route = fc_output.model_route.value
            complexity = fc_output.complexity.value

            # CRITICAL: Trivial/simple requests ALWAYS use fast model (llama3.2:3b)
            # Only coding/trading tasks use qwen3:4b regardless of complexity
            _quality_tasks = {"coding_task", "trading_task"}

            # Fast-conversation patterns: always llama3.2:3b
            _text_lower = text.lower().strip()
            _fast_patterns = (
                "hello", "hi ", "hi!", "hey", "how are you", "thank you",
                "good morning", "good night", "good evening", "good afternoon",
                "what time", "who are you", "what's up", "what's your name",
                "tell me a ", "tell me something", "joke",
                "bye", "goodbye", "see you", "thanks",
                "ok", "okay", "yes", "no ", "sure",
                "what's 2", "what is 2", "two plus",
                "my name is", "i am ", "i'm ",
            )
            _is_fast_conversation = (
                task_type in ("conversation", "direct_knowledge")
                and "explain" not in _text_lower
                and "design" not in _text_lower
                and "debug" not in _text_lower
                and "architect" not in _text_lower
            ) or any(_text_lower.startswith(p) or _text_lower == p.rstrip(" !") for p in _fast_patterns)

            # Deterministic route: skip LLM entirely, return direct response
            if route == "deterministic":
                model = None
                # Build a direct confirmation response for desktop/browser actions
                _action_map = {
                    "browser_action": f"Confirmed: executing '{text}'.",
                    "desktop_action": f"Confirmed: executing '{text}'.",
                    "file_task": f"Confirmed: executing '{text}'.",
                }
                direct_response = _action_map.get(task_type, f"Confirmed: {text}.")
                full_response = direct_response
                yield _json.dumps({"type": "chunk", "text": direct_response}) + "\n"
                total_latency_ms = (_time.perf_counter() - request_start) * 1000
                yield _json.dumps({
                    "type": "done",
                    "text": direct_response,
                    "model": "deterministic",
                    "total_latency_ms": round(total_latency_ms, 1),
                }) + "\n"
                return

            if route == "local_vision" or task_type == "vision_task":
                model = provider.get_model_for_role("vision")
            elif task_type in _quality_tasks:
                model = provider.get_model_for_role("reasoning")
            elif _is_fast_conversation:
                model = provider.get_model_for_role("conversation")
            elif complexity == "complex":
                model = provider.get_model_for_role("reasoning")
            elif route == "local_large":
                model = provider.get_model_for_role("reasoning")
            elif route == "local_small":
                model = provider.get_model_for_role("conversation")
            # else: use default model (llama3.2:3b)

            # Build system prompt based on intent
            system_prompt = _build_system_prompt(task_type, fc_output.complexity.value)

            # Build user prompt with conversation context — limit to 5 turns for voice speed
            context = req.context or {}
            conversation_history = context.get("conversation_history", [])
            max_history = 5 if (req.source == "voice_bridge") else 10
            user_prompt = ""
            for turn in conversation_history[-max_history:]:
                role = turn.get("role", "user")
                t = turn.get("text", "")
                user_prompt += f"{role}: {t}\n"
            user_prompt += f"user: {text}"

            # Stream from provider — pass is_voice + intent for parameter optimization
            full_response = ""
            stream_kwargs = {"model": model} if model else {}
            if req.source == "voice_bridge":
                stream_kwargs["is_voice"] = True
                stream_kwargs["intent"] = task_type
            for chunk in provider.stream_generate(system_prompt, user_prompt, **stream_kwargs):
                full_response += chunk
                yield _json.dumps({"type": "chunk", "text": chunk}) + "\n"

            total_latency_ms = (_time.perf_counter() - request_start) * 1000
            yield _json.dumps({
                "type": "done",
                "text": full_response,
                "model": model or provider.model,
                "total_latency_ms": round(total_latency_ms, 1),
            }) + "\n"

        except Exception as e:
            log.warning("[Brain Stream] Error: %s", e)
            yield _json.dumps({"type": "error", "message": str(e)}) + "\n"
            yield _json.dumps({"type": "done", "text": ""}) + "\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _build_system_prompt(intent: str, complexity: str) -> str:
    """Build an intent-aware system prompt. Optimized for voice: short, direct."""
    base = "You are MYRAA, a helpful desktop AI assistant."

    intent_prompts = {
        "conversation": f"{base} Be brief and natural. One or two sentences max. Sound conversational, not robotic.",
        "local_reasoning": f"{base} Think step by step. Be clear and concise.",
        "direct_knowledge": f"{base} Answer accurately and concisely. No preamble.",
        "coding_task": f"{base} Expert programmer. Write clean code. Explain your approach briefly.",
        "trading_task": f"{base} Financial analyst. Brief insights. Not financial advice.",
        "vision_task": f"{base} Analyze screenshots. Describe what you see concisely.",
        "web_research": f"{base} Synthesize research into a clear, direct answer.",
        "current_information": f"{base} Provide current, accurate answers. Be direct.",
        "weather_task": f"{base} Report weather concisely. Temperature, conditions, one sentence.",
        "news_task": f"{base} Summarize news briefly. Key facts only.",
        "desktop_action": f"{base} Confirm the action briefly.",
        "browser_action": f"{base} Confirm the action briefly.",
        "file_task": f"{base} Confirm the action briefly.",
    }

    prompt = intent_prompts.get(intent, f"{base} Be concise and helpful.")

    if complexity == "complex":
        prompt += " Take your time for complex tasks."
    elif complexity == "trivial":
        prompt += " One sentence max."

    return prompt


_fallback_assistant_runtime = None


def _assistant_runtime():
    """Return the container's AssistantRuntime, or a lazily-built
    standalone instance when the app is used without its lifespan
    (direct endpoint invocation in tests)."""
    global _fallback_assistant_runtime
    if container is not None and getattr(container, "assistant_runtime", None) is not None:
        return container.assistant_runtime
    if _fallback_assistant_runtime is None:
        from .brain.assistant_runtime import AssistantRuntime
        from .brain.super_brain import SuperBrain

        log.warning("/brain used without lifespan; building standalone AssistantRuntime")
        _fallback_assistant_runtime = AssistantRuntime(super_brain=SuperBrain())
    return _fallback_assistant_runtime

# ==========================================================
# Phase A: Project Builder Endpoint
# ==========================================================

class ProjectRequest(BaseModel):
    text: str
    project_name: Optional[str] = None
    mode: Optional[str] = None
    request_id: Optional[str] = None


class ProjectResponse(BaseModel):
    ok: bool
    result: Optional[Any] = None
    error: Optional[str] = None


@app.post("/project", response_model=ProjectResponse)
def project_endpoint(req: ProjectRequest):
    """Phase A: Project Builder -- create, continue, debug, test, document projects."""
    from .brain.metrics import telemetry
    from .brain.super_brain.project_builder_engine import ProjectBuilderEngine, ProjectBuildRequest

    request_id = getattr(req, "request_id", None) or "-"
    start_t = time.perf_counter()

    try:
        engine = ProjectBuilderEngine(container)

        class _Goal:
            def __init__(self, text):
                self.text = text

        goal = _Goal(req.text)
        context = {}

        result = engine.execute(goal, context)

        telemetry.record(
            request_id=request_id,
            component="project_builder",
            route="/project",
            status="ok" if result.get("success") else "error",
            latency_ms=(time.perf_counter() - start_t) * 1000,
        )

        return ProjectResponse(
            ok=result.get("success", False),
            result=result,
        )

    except Exception as e:
        log.exception("Project Builder failed")
        telemetry.record(
            request_id=request_id,
            component="project_builder",
            route="/project",
            status="error",
            latency_ms=(time.perf_counter() - start_t) * 1000,
        )
        return ProjectResponse(ok=False, error=str(e))


@app.get("/projects")
def list_projects():
    """List all active projects."""
    from .brain.super_brain.project_manager import ProjectManager
    pm = ProjectManager()
    return {"projects": pm.list_projects()}


# ==========================================================
# Phase B: Autonomy Controller Endpoints
# ==========================================================

class AutonomyRequest(BaseModel):
    text: str
    level: Optional[str] = "autonomous"  # guided | balanced | autonomous
    max_iterations: Optional[int] = None
    max_retries: Optional[int] = None
    max_execution_time_s: Optional[float] = None
    success_criteria: Optional[List[str]] = None
    constraints: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None


class AutonomyControlRequest(BaseModel):
    goal_id: str


class AutonomyResponse(BaseModel):
    ok: bool
    goal_id: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None


@app.post("/autonomy", response_model=AutonomyResponse)
def autonomy_start(req: AutonomyRequest):
    """Phase B: Start an autonomous goal execution."""
    from .brain.super_brain.autonomy_controller import (
        AutonomyController,
        AutonomyLevel,
        LoopGuards,
    )

    request_id = getattr(req, "request_id", None) or "-"
    start_t = time.perf_counter()

    try:
        ac = container.autonomy_controller

        level_map = {
            "guided": AutonomyLevel.GUIDED,
            "balanced": AutonomyLevel.BALANCED,
            "autonomous": AutonomyLevel.AUTONOMOUS,
        }
        level = level_map.get(req.level or "autonomous", AutonomyLevel.AUTONOMOUS)

        guards = LoopGuards()
        if req.max_iterations is not None:
            guards.max_iterations = req.max_iterations
        if req.max_retries is not None:
            guards.max_total_retries = req.max_retries
            guards.max_retries_per_task = req.max_retries
        if req.max_execution_time_s is not None:
            guards.max_execution_time_s = req.max_execution_time_s

        goal = ac.start_goal(
            user_request=req.text,
            level=level,
            guards=guards,
            success_criteria=req.success_criteria,
            constraints=req.constraints,
        )

        # Execute the goal (synchronous for now, async wrapper possible)
        goal = ac.execute_goal(goal)

        from .brain.metrics import telemetry
        telemetry.record(
            request_id=request_id,
            component="autonomy",
            route="/autonomy",
            status="ok" if goal.state.value == "completed" else "error",
            latency_ms=(time.perf_counter() - start_t) * 1000,
        )

        return AutonomyResponse(
            ok=goal.state.value == "completed",
            goal_id=goal.goal_id,
            result=goal.to_dict(),
        )

    except Exception as e:
        log.exception("Autonomy execution failed")
        from .brain.metrics import telemetry
        telemetry.record(
            request_id=request_id,
            component="autonomy",
            route="/autonomy",
            status="error",
            latency_ms=(time.perf_counter() - start_t) * 1000,
        )
        return AutonomyResponse(ok=False, error=str(e))


@app.get("/autonomy/status")
def autonomy_status():
    """Get overall autonomy system status."""
    from .brain.super_brain.autonomy_controller import AutonomyController
    ac = container.autonomy_controller
    return ac.status()


@app.get("/autonomy/goals")
def autonomy_list_goals():
    """List all autonomous goals."""
    from .brain.super_brain.autonomy_controller import AutonomyController
    ac = container.autonomy_controller
    return {"goals": ac.list_goals()}


@app.get("/autonomy/goals/{goal_id}")
def autonomy_get_goal(goal_id: str):
    """Get detailed status of a specific autonomous goal."""
    from .brain.super_brain.autonomy_controller import AutonomyController
    ac = container.autonomy_controller
    goal = ac.get_goal(goal_id)
    if not goal:
        return {"error": "goal not found"}
    return goal.to_dict()


@app.get("/autonomy/goals/{goal_id}/progress")
def autonomy_progress(goal_id: str):
    """Get detailed progress report for a goal."""
    from .brain.super_brain.autonomy_controller import AutonomyController
    ac = container.autonomy_controller
    report = ac.progress_report(goal_id)
    if not report:
        return {"error": "goal not found"}
    return report


@app.get("/autonomy/goals/{goal_id}/telemetry")
def autonomy_telemetry(goal_id: str):
    """Get telemetry for a specific goal."""
    from .brain.super_brain.autonomy_controller import AutonomyController
    ac = container.autonomy_controller
    telem = ac.telemetry(goal_id)
    if not telem:
        return {"error": "goal not found"}
    return telem


@app.post("/autonomy/pause", response_model=AutonomyResponse)
def autonomy_pause(req: AutonomyControlRequest):
    """Pause an autonomous goal."""
    from .brain.super_brain.autonomy_controller import AutonomyController
    ac = container.autonomy_controller
    ok = ac.pause(req.goal_id)
    return AutonomyResponse(ok=ok, goal_id=req.goal_id, result="paused" if ok else "not found")


@app.post("/autonomy/resume", response_model=AutonomyResponse)
def autonomy_resume(req: AutonomyControlRequest):
    """Resume a paused autonomous goal."""
    from .brain.super_brain.autonomy_controller import AutonomyController
    ac = container.autonomy_controller
    ok = ac.resume(req.goal_id)
    return AutonomyResponse(ok=ok, goal_id=req.goal_id, result="resumed" if ok else "not found")


@app.post("/autonomy/cancel", response_model=AutonomyResponse)
def autonomy_cancel(req: AutonomyControlRequest):
    """Cancel an autonomous goal."""
    from .brain.super_brain.autonomy_controller import AutonomyController
    ac = container.autonomy_controller
    ok = ac.cancel(req.goal_id)
    return AutonomyResponse(ok=ok, goal_id=req.goal_id, result="cancelled" if ok else "not found")


@app.get("/autonomy/checkpoints")
def autonomy_checkpoints():
    """List persisted autonomy checkpoints."""
    from .brain.super_brain.autonomy_controller import AutonomyController
    ac = container.autonomy_controller
    return {"checkpoints": ac.list_checkpoints()}


@app.post("/autonomy/resume-checkpoint", response_model=AutonomyResponse)
def autonomy_resume_checkpoint(req: AutonomyControlRequest):
    """Resume a goal from a persisted checkpoint."""
    from .brain.super_brain.autonomy_controller import AutonomyController
    ac = container.autonomy_controller
    goal = ac.load_checkpoint(req.goal_id)
    if not goal:
        return AutonomyResponse(ok=False, error="checkpoint not found")
    goal = ac.execute_goal(goal)
    return AutonomyResponse(
        ok=goal.state.value == "completed",
        goal_id=goal.goal_id,
        result=goal.to_dict(),
    )


# ==========================================================
# Phase C: Vision Endpoints
# ==========================================================

@app.get("/vision/status")
def vision_status():
    """Get continuous vision pipeline status and frame health."""
    cv = container.continuous_vision
    return cv.status_report()


@app.get("/vision/telemetry")
def vision_telemetry():
    """Get lightweight vision telemetry for UI."""
    cv = container.continuous_vision
    return cv.telemetry()


@app.get("/vision/state")
def vision_state():
    """Get current structured visual state."""
    cv = container.continuous_vision
    state = cv.get_current_state()
    if state is None:
        return {"error": "no visual state available"}
    return state.to_dict()


@app.get("/vision/context")
def vision_context():
    """Get visual context for ContextFusion injection."""
    cv = container.continuous_vision
    ctx = cv.get_context_for_fusion()
    if ctx is None:
        return {"error": "no visual context available (stale or not started)"}
    return ctx


class VisionVerifyRequest(BaseModel):
    expected: Dict[str, Any]


@app.post("/vision/verify")
def vision_verify(req: VisionVerifyRequest):
    """Visual verification: check if screen matches expected state."""
    cv = container.continuous_vision
    return cv.verify_action(req.expected)


@app.get("/health/multimodal")
def multimodal_health():
    """Multimodal health: vision + voice + autonomy + research status."""
    health = {}

    # Vision
    try:
        cv = container.continuous_vision
        health["vision"] = {
            "status": cv.status.value,
            "healthy": cv.is_healthy(),
            "stale": cv.is_stale(),
            "frames": cv.health.total_frames,
        }
    except Exception as e:
        log.warning("Vision health check failed: %s", e)
        health["vision"] = {"status": "unavailable", "healthy": False}

    # Voice (Node-side voice transport — check via agent health)
    try:
        cvl = container.continuous_voice_loop
        health["voice"] = cvl.status()
    except Exception:
        health["voice"] = {
            "status": "active",
            "provider": "voice_bridge",
            "note": "Node-side voice bridge (server.ts /live WebSocket)",
        }

    # Autonomy
    try:
        ac = container.autonomy_controller
        health["autonomy"] = ac.status()
    except Exception:
        health["autonomy"] = {"status": "unavailable"}

    # Memory
    try:
        health["memory"] = {
            "status": "active",
            "count": container.memory_2_0.get_active_count(),
        }
    except Exception:
        health["memory"] = {"status": "unavailable"}

    # SuperBrain
    try:
        health["super_brain"] = container.super_brain.status()
    except Exception:
        health["super_brain"] = {"status": "unavailable"}

    # Desktop Agent
    try:
        import requests
        resp = requests.get("http://127.0.0.1:8765/health/live", timeout=2)
        health["desktop_agent"] = {"status": "healthy" if resp.ok else "degraded"}
    except Exception:
        health["desktop_agent"] = {"status": "unreachable"}

    # Telemetry relay
    try:
        from .brain.telemetry.relay import telemetry_relay
        health["telemetry_relay"] = telemetry_relay.status()
    except Exception:
        health["telemetry_relay"] = {"status": "unavailable"}

    return health


# ---------------------------------------------------------------------------
# Telemetry Relay endpoints — polled by Node server.ts for WS broadcast.
# ---------------------------------------------------------------------------

@app.get("/telemetry/drain")
def telemetry_drain():
    """Return AND clear all buffered telemetry events (for Node polling)."""
    from .brain.telemetry.relay import telemetry_relay
    events = telemetry_relay.drain()
    return {"events": events, "count": len(events)}


@app.get("/telemetry/stream")
def telemetry_stream(count: int = 50):
    """Return the last N telemetry events without clearing (non-destructive)."""
    from .brain.telemetry.relay import telemetry_relay
    events = telemetry_relay.stream(count=min(count, 200))
    return {"events": events, "count": len(events)}


@app.get("/telemetry/status")
def telemetry_status():
    """Telemetry relay health check."""
    from .brain.telemetry.relay import telemetry_relay
    return telemetry_relay.status()


@app.post("/telemetry/emit")
def telemetry_emit(event_type: str, payload: Dict[str, Any]):
    """Allow Node or other services to inject telemetry events into the relay."""
    from .brain.telemetry.relay import telemetry_relay, REQUEST_STARTED
    if not event_type:
        event_type = REQUEST_STARTED
    event = telemetry_relay.emit(event_type, payload)
    return {"ok": True, "event_type": event.event_type, "timestamp": event.timestamp}


# ---------------------------------------------------------------------------
# Continuous Voice Loop endpoints — called by Node server.ts.
# ---------------------------------------------------------------------------

class VoiceTranscriptRequest(BaseModel):
    transcript: str

class VoiceTurnRequest(BaseModel):
    turn_id: Optional[str] = None


@app.get("/voice/health")
def voice_health():
    """Voice loop health for Node polling."""
    cvl = container.continuous_voice_loop
    return cvl.health()


@app.get("/voice/status")
def voice_status():
    """Lightweight voice status."""
    cvl = container.continuous_voice_loop
    return cvl.status()


@app.post("/voice/transcript")
def voice_transcript(req: VoiceTranscriptRequest):
    """Process a user transcript through the voice loop."""
    cvl = container.continuous_voice_loop
    return cvl.on_user_transcript(req.transcript)


@app.post("/voice/interrupt")
def voice_interrupt():
    """Handle barge-in / interruption."""
    cvl = container.continuous_voice_loop
    return cvl.on_interruption()


@app.post("/voice/turn-complete")
def voice_turn_complete():
    """Mark TTS turn complete, return to LISTENING."""
    cvl = container.continuous_voice_loop
    return cvl.on_turn_complete()


@app.post("/voice/disconnect")
def voice_disconnect():
    """Handle voice pipe disconnection."""
    cvl = container.continuous_voice_loop
    return cvl.on_disconnect()


@app.post("/voice/reconnect")
def voice_reconnect():
    """Recover from disconnection."""
    cvl = container.continuous_voice_loop
    return cvl.on_reconnect()


@app.get("/voice/ticks")
def voice_tick():
    """Periodic maintenance: check timeouts, clean up zombies.

    Node should call this every ~5 seconds.
    """
    cvl = container.continuous_voice_loop
    return cvl.tick()


@app.get("/voice/turns")
def voice_turns(count: int = 10):
    """Return recent turns."""
    cvl = container.continuous_voice_loop
    return {"turns": cvl.get_recent_turns(count)}


class VoiceExecuteRequest(BaseModel):
    transcript: str
    function_name: Optional[str] = None
    function_args: Optional[dict] = None
    request_id: Optional[str] = None
    turn_id: Optional[str] = None


@app.post("/voice/execute")
def voice_execute(req: VoiceExecuteRequest):
    """Unified voice execution — routes through AssistantRuntime.

    This is the canonical entry point for ALL voice requests.
    Voice transcripts converge here from the Gemini Live session.
    """
    from desktop_agent.brain.assistant_runtime import (
        AssistantRequest,
        InputType,
    )
    import uuid
    import time as _time

    request_id = req.request_id or f"vr-{uuid.uuid4().hex[:12]}"
    turn_id = req.turn_id or f"vt-{uuid.uuid4().hex[:8]}"

    # Build the user input — include function call context if present
    user_input = req.transcript
    if req.function_name:
        user_input = f"[Voice action: {req.function_name}({json.dumps(req.function_args or {})})] {req.transcript}"

    vreq = AssistantRequest(
        user_input=user_input,
        input_type=InputType.VOICE,
        source="voice_bridge",
        request_id=request_id,
        session_id="voice",
    )

    t_start = _time.monotonic()
    try:
        vresp = container.assistant_runtime.handle(vreq)
        brain_ms = (_time.monotonic() - t_start) * 1000
        return {
            "ok": bool(vresp.ok),
            "message": vresp.message,
            "decision": vresp.decision,
            "task_id": vresp.task_id,
            "request_id": vresp.request_id,
            "turn_id": turn_id,
            "tool_used": getattr(vresp, "tool_used", None),
            "brain_ms": round(brain_ms, 1),
        }
    except AttributeError:
        # Container not fully initialized (test context)
        return {
            "ok": False,
            "error": "assistant_runtime_not_available",
            "turn_id": turn_id,
            "request_id": request_id,
        }
    except Exception as exc:
        log.warning("[VoiceExecute] Error: %s", exc)
        return {
            "ok": False,
            "error": str(exc),
            "turn_id": turn_id,
            "request_id": request_id,
        }

@app.post("/voice/tts")
def voice_tts(req: dict):
    """RETIRED (Gemini Live migration): compatibility wrapper, never launches TTS."""
    return {"ok": False, "deprecated": True, "replacement": "gemini_live",
            "error": "Use the Gemini Live voice session."}


@app.post("/voice/tts/stream")
def voice_tts_stream(req: dict):
    """RETIRED (Gemini Live migration): compatibility wrapper, never launches TTS."""
    return {"ok": False, "deprecated": True, "replacement": "gemini_live",
            "error": "Use the Gemini Live voice session."}


# NOTE (Gemini Live migration): no local-provider warm exists. Voice warmup
# verifies Gemini configuration only; see voice_warmup below.


@app.post("/voice/warmup")
def voice_warmup():
    """Warm up Ollama models to reduce cold-start latency.

    Sends a minimal request to keep qwen3:4b loaded in VRAM.
    Sets keep_alive=30min to prevent model eviction.
    Called periodically by Node on startup and idle intervals.

    Voice warmup is Gemini-only: verifies GEMINI_API_KEY + SDK + model
    configuration. NEVER initializes any retired STT/TTS provider,
    never opens a realtime session, never consumes quota.
    """
    from .speech.gemini_live import load_gemini_live_config

    cfg = load_gemini_live_config()
    voice = {"provider": "gemini_live", "configured": cfg.configured,
             "model": cfg.model if cfg.configured else ""}
    if not cfg.configured:
        voice["error"] = "GEMINI_API_KEY is not configured."
    import os
    import requests as _requests

    ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    try:
        from .config.settings import GENERAL_MODEL
        model = GENERAL_MODEL  # llama3.2:3b — primary voice model
    except ImportError:
        model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

    try:
        # Check if Ollama is running
        resp = _requests.get(f"{ollama_url}/api/tags", timeout=3)
        if resp.status_code != 200:
            return {"ok": False, "error": "Ollama not reachable", "voice": voice}

        # Warm model with keep_alive=30min to prevent eviction
        gen_resp = _requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": model,
                "prompt": "hi",
                "options": {"num_predict": 1, "num_ctx": 4096},
                "keep_alive": 1800,  # 30 minutes
                "think": False,
            },
            timeout=15,
        )
        if gen_resp.status_code == 200:
            return {"ok": True, "model": model, "status": "warm", "keep_alive": "30min", "voice": voice}
        else:
            return {"ok": False, "error": f"Ollama generate returned {gen_resp.status_code}", "voice": voice}

    except Exception as e:
        return {"ok": False, "error": str(e), "voice": voice}


@app.get("/models/health")
def models_health():
    """Model health status — shows routing, health, and installed models."""
    try:
        from .brain.ai.providers.ollama_provider import OllamaProvider
        provider = OllamaProvider()
        provider.available()  # refresh available_models list
        return {
            "ok": True,
            "model_status": provider.model_status(),
            "available_models": provider._available_models,
            "default_model": provider.model,
            "fallback_model": provider._fallback_model,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/voice/stt")
def voice_stt(req: dict):
    """RETIRED (Gemini Live migration): compatibility wrapper, never launches STT."""
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=410, content={
        "ok": False, "deprecated": True, "replacement": "gemini_live",
        "error": {"code": "VOICE_RETIRED", "message": "Use the Gemini Live voice session.", "retryable": False}})


# NOTE (Gemini Live migration): the old VoiceProviderManager singleton is gone.
# Gemini Live is the only voice provider; see load_gemini_live_config.


@app.post("/voice/stt/local")
def voice_stt_local(req: dict):
    """RETIRED (Gemini Live migration): compatibility wrapper, never launches STT engines."""
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=410, content={
        "ok": False, "deprecated": True, "replacement": "gemini_live",
        "error": {"code": "VOICE_RETIRED", "message": "Use the Gemini Live voice session.", "retryable": False}})


@app.post("/voice/tts/local")
def voice_tts_local(req: dict):
    """RETIRED (Gemini Live migration): compatibility wrapper, never launches TTS."""
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=410, content={
        "ok": False, "deprecated": True, "replacement": "gemini_live",
        "error": {"code": "VOICE_RETIRED", "message": "Use the Gemini Live voice session.", "retryable": False}})


@app.post("/voice/echo/note")
def voice_echo_note(req: dict):
    """RETIRED (Gemini Live migration): compatibility wrapper (no-op)."""
    return {"ok": True, "deprecated": True, "replacement": "gemini_live"}


@app.post("/voice/echo/check")
def voice_echo_check(req: dict):
    """RETIRED (Gemini Live migration): compatibility wrapper (no-op)."""
    return {"rejected": False, "deprecated": True, "replacement": "gemini_live"}


@app.post("/voice/tts/cancel")
def voice_tts_cancel():
    """RETIRED (Gemini Live migration): compatibility wrapper (no-op)."""
    return {"ok": True, "deprecated": True, "replacement": "gemini_live"}


@app.get("/voice/providers/health")
def voice_providers_health():
    """Gemini-only voice health. Old providers are never reported."""
    from .speech.gemini_live import load_gemini_live_config

    cfg = load_gemini_live_config()
    d = cfg.describe()
    d["connected"] = _gemini_bridges_active > 0
    return {"voice": d}


@app.get("/voice/gemini/health")
def voice_gemini_health():
    """Gemini Live voice health — the ONLY active voice provider (§30).

    Never exposes the API key. Reports configured/model/connected plus the
    full session/manager health snapshot (§18): state, generation, counters,
    activity ages, event-loop starvation evidence. Read-only.
    """
    from .speech.gemini_live import load_gemini_live_config

    cfg = load_gemini_live_config()
    d = cfg.describe()
    # No per-process session snapshot: each bridge owns its manager (no
    # singleton). Connection truth is the active-bridge count below.
    d["connected"] = _gemini_bridges_active > 0
    d["bridges_active"] = _gemini_bridges_active
    d["bridge"] = dict(_gemini_bridge_stats())
    return {"voice": d}


# Active Gemini bridge count (replaces the old per-process singleton alias,
# which concurrent bridges clobbered). Incremented per open bridge, decremented
# on close. Single asyncio loop: plain int mutation is safe.
_gemini_bridges_active = 0


# §14 bridge counters (aggregate only — never per-chunk logging).
_gemini_bridge_counters = {
    "chunks_in": 0, "bytes_in": 0, "events_out": 0, "speak_in": 0,
    "events_dropped": 0,
}


class _BridgeEventQueues:
    """Bounded bridge fan-out: control events never drop; audio/partial
    (high-volume, loss-tolerant — the next chunk supersedes a dropped one)
    drop oldest beyond MEDIA_MAX. Prevents unbounded growth if Node reads
    slower than Gemini emits, without ever losing lifecycle events
    (connection_failed, turn_complete, interrupted, errors, resumption).
    """

    MEDIA_MAX = 128
    MEDIA_KINDS = frozenset({"audio", "partial"})

    def __init__(self) -> None:
        self.control: asyncio.Queue = asyncio.Queue()
        self.media: asyncio.Queue = asyncio.Queue(maxsize=self.MEDIA_MAX)
        self.dropped_media = 0

    async def put(self, ev) -> None:
        if getattr(ev, "kind", "") in self.MEDIA_KINDS:
            try:
                self.media.put_nowait(ev)
            except asyncio.QueueFull:
                try:
                    self.media.get_nowait()  # drop oldest media
                except asyncio.QueueEmpty:
                    pass
                else:
                    self.dropped_media += 1
                    _gemini_bridge_counters["events_dropped"] += 1
                try:
                    self.media.put_nowait(ev)
                except asyncio.QueueFull:
                    self.dropped_media += 1
                    _gemini_bridge_counters["events_dropped"] += 1
        else:
            await self.control.put(ev)


def _gemini_bridge_stats() -> dict:
    return dict(_gemini_bridge_counters)


@app.websocket("/voice/gemini/stream")
async def voice_gemini_stream_ws(websocket: WebSocket):
    """Node <-> Python Gemini Live bridge (authoritative realtime path, §32).

    Node -> Python: {"type": "audio", "audio": base64 PCM16 mono 16k}
                    {"type": "speak", "text": canonical response to vocalize}
                    {"type": "stop"}
    Python -> Node: {"type": "connected"} | {"type": "session_started", ...}
                    {"type": "partial_transcript", "role", "text"}
                    {"type": "audio", "audio": base64 PCM16 24k}
                    {"type": "interrupted", ...} | {"type": "turnComplete", ...}
                    {"type": "tool_result", ...} | {"type": "error", ...}
    """
    import base64 as _b64

    from .speech.gemini_live import (
        GeminiLiveSessionManager,
        GeminiVoiceMetrics,
        classify_gemini_error,
        load_gemini_live_config,
    )

    global _gemini_bridges_active

    await websocket.accept()
    _gemini_bridges_active += 1
    cfg = load_gemini_live_config()
    if not cfg.configured:
        await websocket.send_text(json.dumps({
            "type": "error", "code": "GEMINI_CONFIGURATION_ERROR",
            "message": "GEMINI_API_KEY is not configured.", "retryable": False,
        }))
        await websocket.close(code=1011, reason="Gemini not configured")
        return

    metrics = GeminiVoiceMetrics()
    queues = _BridgeEventQueues()

    async def _on_event(ev) -> None:
        await queues.put(ev)

    manager = GeminiLiveSessionManager(cfg, on_event=_on_event)
    try:
        try:
            await manager.start()
        except Exception as e:
            from .speech.gemini_live import GeminiErrorCode

            code = classify_gemini_error(e)
            await websocket.send_text(json.dumps({
                "type": "error", "code": code.value,
                "message": f"Gemini Live connection failed ({code.value}).",
                "retryable": code in (GeminiErrorCode.GEMINI_NETWORK_ERROR,
                                      GeminiErrorCode.GEMINI_SESSION_ERROR),
            }))
            await websocket.close(code=1011, reason="Gemini connect failed")
            return

        async def _pump_out():
            # Control events always drain first: lifecycle signals (turn
            # completion, interruption, failure, resumption) can never be
            # stuck behind a media burst.
            async def _send(ev) -> bool:
                msg = _gemini_event_to_node(ev)
                if msg is None:
                    return True
                _gemini_bridge_counters["events_out"] += 1
                try:
                    await websocket.send_text(json.dumps(msg))
                except Exception:
                    return False
                return True

            while True:
                while True:
                    try:
                        ev = queues.control.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    if not await _send(ev):
                        return
                ev = await queues.media.get()
                if not await _send(ev):
                    return

        async def _pump_in():
            async for raw in websocket.iter_text():
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                t = data.get("type", "")
                sess = manager.session
                if t == "stop":
                    break
                if sess is None:
                    continue
                if t == "audio":
                    b64 = data.get("audio", "")
                    if not b64:
                        continue
                    try:
                        pcm = _b64.b64decode(b64)
                    except Exception:
                        continue
                    _gemini_bridge_counters["chunks_in"] += 1
                    _gemini_bridge_counters["bytes_in"] += len(pcm)
                    # Non-blocking handoff to the session's bounded queue.
                    # submit_audio drops (and counts) when not READY — this
                    # call site can NEVER produce a send error storm.
                    sess.submit_audio(pcm)
                elif t == "speak":
                    text = (data.get("text", "") or "").strip()
                    if text:
                        _gemini_bridge_counters["speak_in"] += 1
                        try:
                            await sess.speak_text(text)
                        except Exception as e:
                            log.warning("[GeminiLive] speak_text failed: %s", e)

        out_task = asyncio.create_task(_pump_out())
        try:
            await _pump_in()
        finally:
            out_task.cancel()
            try:
                await out_task
            except asyncio.CancelledError:
                pass
    finally:
        if _gemini_bridges_active > 0:
            _gemini_bridges_active -= 1
        try:
            await manager.stop()
        except Exception:
            pass


def _gemini_event_to_node(ev) -> Optional[dict]:
    """Translate GeminiLiveSession events to the Node wire protocol."""
    import base64 as _b64

    k, d = ev.kind, ev.data
    if k in ("connected", "session_started"):
        out = {"type": k}
        out.update({kk: vv for kk, vv in d.items() if kk in ("session_id", "model")})
        return out
    if k == "partial":
        return {"type": "partial_transcript", "role": d.get("role", "user"),
                "text": d.get("text", "")}
    if k == "audio":
        raw = d.get("audio", b"")
        return {"type": "audio",
                "audio": _b64.b64encode(bytes(raw)).decode("ascii"),
                "generation": d.get("generation", "")}
    if k == "interrupted":
        return {"type": "interrupted", "generation": d.get("generation", "")}
    if k == "turn_complete":
        return {"type": "turnComplete", "turn_id": d.get("turn_id", "")}
    if k == "tool_result":
        return {"type": "tool_result", "id": d.get("id", ""),
                "name": d.get("name", ""), "ok": d.get("ok", False)}
    if k == "go_away":
        return {"type": "reconnecting", "reason": "go_away"}
    if k == "connection_failed":
        return {"type": "connection_failed", "reason": d.get("reason", ""),
                "generation": d.get("generation", 0)}
    if k == "reconnecting":
        return {"type": "reconnecting", "attempt": d.get("attempt", 0)}
    if k == "reconnected":
        return {"type": "reconnected", "generation": d.get("generation", 0)}
    if k == "closed":
        return None
    if k == "error":
        return {"type": "error", "code": d.get("code", "GEMINI_UNKNOWN_ERROR"),
                "message": d.get("message", "Gemini Live error"), "retryable": False}
    return None


@app.websocket("/voice/stt/stream")
async def voice_stt_stream_ws(websocket: WebSocket):
    """RETIRED (Gemini Live migration): legacy voice bridge.

    Accepts, reports the retired-path error, and closes. No legacy provider
    code is reachable from this endpoint; /voice/gemini/stream is the only
    active voice path.
    """
    await websocket.accept()
    await websocket.send_text(json.dumps({
        "type": "error", "code": "VOICE_RETIRED",
        "error": "Use the Gemini Live voice session (/voice/gemini/stream).",
        "retryable": False,
    }))
    await websocket.close(code=1011, reason="Retired voice path")


@app.get("/trading/status")
def trading_status():
    """Trading Intelligence Engine status."""
    return container.trading_engine.status()


@app.get("/trading/thesis")
def trading_thesis_history(symbol: Optional[str] = None, limit: int = 20):
    """Get trade thesis history."""
    return {"theses": container.trading_engine.get_thesis_history(symbol, limit)}


@app.get("/trading/paper/stats")
def trading_paper_stats():
    """Get paper trading statistics."""
    return container.trading_engine.paper_stats()


@app.get("/trading/paper/open")
def trading_paper_open():
    """Get open paper trades."""
    from dataclasses import asdict
    trades = container.trading_engine._paper_trader.get_open_trades()
    return {"trades": [asdict(t) for t in trades]}


@app.get("/trading/broker/account")
def trading_broker_account():
    """Get broker account status (read-only)."""
    return container.trading_engine.broker_account()


# ==========================================================
# Phase D Part 2: Groww Professional Trading Advisor
# ==========================================================

@app.get("/groww/status")
def groww_status():
    """Groww advisor connection and portfolio status."""
    return {
        "state": container.groww_advisor.state,
        "health": container.groww_advisor.health(),
    }


@app.get("/groww/portfolio")
def groww_portfolio():
    """Sync and return Groww portfolio (holdings + positions)."""
    snapshot = container.groww_advisor.sync_portfolio()
    from dataclasses import asdict
    return {
        "snapshot": asdict(snapshot),
        "broker": "groww",
        "connected": container.groww_advisor.connected,
    }


@app.get("/groww/analyze")
def groww_analyze(market_context: str = ""):
    """Personalized portfolio analysis: 'Mere portfolio ko analyze karo'."""
    advice = container.groww_advisor.analyze_my_portfolio(market_context)
    from dataclasses import asdict
    return asdict(advice)


@app.get("/groww/stock/{symbol}")
def groww_stock_guidance(symbol: str):
    """Personalized guidance for a specific stock."""
    guidance = container.groww_advisor.get_stock_advice(symbol)
    from dataclasses import asdict
    return asdict(guidance)


@app.get("/groww/quote/{symbol}")
def groww_quote(symbol: str):
    """Live quote from Groww for a specific stock."""
    quote = container.groww_advisor.get_live_quote(symbol)
    if isinstance(quote, dict):
        quote.pop("error", None)
    return {"symbol": symbol, "quote": quote, "broker": "groww"}


@app.get("/groww/options/{underlying}")
def groww_option_chain(underlying: str, expiry: str = ""):
    """Get option chain from Groww."""
    if not expiry:
        return {"error": "expiry_date required", "underlying": underlying}
    chain = container.groww_advisor.get_option_chain(underlying, expiry)
    if chain is None:
        return {"error": "Option chain unavailable", "underlying": underlying}
    from dataclasses import asdict
    return {"chain": asdict(chain), "broker": "groww"}


@app.get("/groww/analyze/{symbol}")
def groww_analyze_stock(symbol: str):
    """Run full Phase D analysis on a stock using Groww quote."""
    return container.groww_advisor.analyze_stock(symbol)


# ==========================================================
# Phase D Final: Alerts, Automation, Health
# ==========================================================

@app.get("/trading/alerts")
def trading_alerts(limit: int = 50, unacknowledged: bool = False):
    """Get trading alerts."""
    return {"alerts": container.alert_engine.get_alerts(limit, unacknowledged)}


@app.get("/trading/alerts/rules")
def trading_alert_rules():
    """Get alert rules."""
    return {"rules": container.alert_engine.get_rules()}


@app.post("/trading/alerts/rules")
def create_alert_rule(rule: Dict[str, Any]):
    """Create an alert rule."""
    from desktop_agent.finance.trading.alerts.engine import AlertRule
    import uuid
    r = AlertRule(
        rule_id=rule.get("rule_id", str(uuid.uuid4())[:8]),
        alert_type=rule.get("alert_type", "portfolio_movement"),
        symbol=rule.get("symbol", ""),
        threshold=rule.get("threshold", 3.0),
        direction=rule.get("direction", "above"),
        description=rule.get("description", ""),
    )
    container.alert_engine.add_rule(r)
    return {"status": "created", "rule_id": r.rule_id}


@app.post("/trading/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str):
    """Acknowledge an alert."""
    container.alert_engine.acknowledge(alert_id)
    return {"status": "acknowledged", "alert_id": alert_id}


@app.get("/trading/alerts/state")
def trading_alerts_state():
    """Alert engine state."""
    return container.alert_engine.state


@app.get("/trading/daily-close")
def trading_daily_close_status():
    """Daily close scheduler status."""
    return container.daily_close_scheduler.state


@app.post("/trading/daily-close/trigger")
def trigger_daily_close():
    """Manually trigger the daily close workflow."""
    result = container.daily_close_scheduler.trigger_now()
    from dataclasses import asdict
    return asdict(result)


@app.get("/trading/health")
def trading_health():
    """Comprehensive trading system health check."""
    groww = container.groww_advisor.health()
    alerts = container.alert_engine.state
    scheduler = container.daily_close_scheduler.state
    engine = container.trading_engine.status()
    return {
        "groww": groww,
        "alerts": alerts,
        "scheduler": scheduler,
        "engine": engine,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ==========================================================
# Neural Intelligence Engine (Phase F)
# ==========================================================


@app.get("/neural/status")
def neural_status():
    """Neural Engine status and telemetry."""
    engine = container.neural_engine
    return {
        "status": "active",
        "telemetry": engine.telemetry.summary(),
        "registered_models": len(engine._models) if hasattr(engine, '_models') else 0,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/neural/models")
def neural_models():
    """List registered neural models."""
    engine = container.neural_engine
    models = []
    if hasattr(engine, '_models'):
        for name, spec in engine._models.items():
            models.append({
                "name": name,
                "domain": getattr(spec, 'domain', 'unknown'),
                "status": getattr(spec, 'status', 'unknown'),
            })
    return {"models": models}


@app.post("/neural/infer")
def neural_infer(request_body: dict):
    """Run neural inference on a request."""
    from desktop_agent.neural_engine.model_contract import InferenceRequest, ModelDomain
    engine = container.neural_engine
    try:
        domain_str = request_body.get("domain", "multimodal")
        try:
            domain = ModelDomain(domain_str)
        except ValueError:
            domain = ModelDomain.MULTIMODAL
        req = InferenceRequest(
            domain=domain,
            input_data=request_body.get("input", ""),
            context=request_body.get("context", {}),
        )
        result = engine.infer(req)
        return {
            "ok": True,
            "result": {
                "output": getattr(result, 'output', ''),
                "confidence": getattr(result, 'confidence', 0.0),
                "model": getattr(result, 'model', 'unknown'),
            },
        }
    except Exception as e:
        log.warning("Neural inference failed: %s", e)
        return {"ok": False, "error": str(e)}


# ==========================================================
# Self-Healing (Phase G)
# ==========================================================


@app.get("/self-healing/status")
def self_healing_status():
    """Self-Healing system status."""
    mgr = container.self_healing
    return mgr.get_system_status()


@app.get("/self-healing/diagnostics")
def self_healing_diagnostics():
    """Run diagnostics on all subsystems."""
    mgr = container.self_healing
    try:
        health = mgr.check_health()
        return {"ok": True, "health": health}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/self-healing/full-report")
def self_healing_full_report():
    """Complete self-healing report."""
    mgr = container.self_healing
    return mgr.get_full_report()


@app.post("/self-healing/diagnose")
def self_healing_diagnose(request_body: dict):
    """Diagnose a specific component failure."""
    mgr = container.self_healing
    component = request_body.get("component", "unknown")
    try:
        analysis = mgr.diagnose_issue(component)
        return {"ok": True, "analysis": analysis}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ==========================================================
# Universal Control (Phase E)
# ==========================================================


@app.get("/universal-control/status")
def universal_control_status():
    """Universal Controller status."""
    ctrl = container.universal_controller
    return {
        "status": "active" if ctrl else "unavailable",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/universal-control/interact")
def universal_control_interact(request_body: dict):
    """Execute a Universal Control interaction."""
    ctrl = container.universal_controller
    if not ctrl:
        return {"ok": False, "error": "Universal Controller not available"}
    intent = request_body.get("intent", "")
    target = request_body.get("target", "")
    try:
        result = ctrl.execute_intent(intent)
        return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _short_args(args: Dict[str, Any]) -> str:
    """Compact, log-safe representation of args (truncate long values)."""
    parts = []
    for k, v in args.items():
        s = repr(v)
        if len(s) > 60:
            s = s[:60] + "…"
        parts.append(f"{k}={s}")
    return "{" + ", ".join(parts) + "}"


def main() -> None:
    """Allow `python -m desktop_agent.main` to launch uvicorn."""
    import uvicorn

    host = os.environ.get("MYRAA_AGENT_HOST", "127.0.0.1")
    port = int(os.environ.get("MYRAA_AGENT_PORT", "8765"))
    log.info("Launching uvicorn on %s:%d", host, port)
    uvicorn.run(
        "desktop_agent.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
