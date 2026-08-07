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

from dataclasses import asdict

from .brain.brain import Brain
from .brain.models import BrainContext

import logging
import os
from desktop_agent.core.application_container import ApplicationContainer
import traceback
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from .brain.execution_brain import ExecutionBrain
from desktop_agent.brain.observer.registry import ObserverRegistry
from desktop_agent.brain.observer.manager import ObserverManager
from desktop_agent.brain.observer.observers.stock_observer import StockObserver

from desktop_agent.finance.finance_service import FinanceService

from desktop_agent.finance.market.provider_manager import ProviderManager
from desktop_agent.finance.market.providers.yahoo_provider import YahooProvider

from desktop_agent.finance.portfolio.portfolio_manager import PortfolioManager


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import __version__
from .registry import DESKTOP_TOOL_NAMES, TOOLS, ToolError, load_all




logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("myraa.desktop")


# Load all tool modules so their handlers register before the app starts.
load_all()
log.info("Loaded %d desktop tools: %s", len(TOOLS), ", ".join(sorted(TOOLS)))

@asynccontextmanager
async def lifespan(app: FastAPI):

    log.info("MYRAA Desktop Control Agent v%s starting.", __version__)

    #
    # Start autonomous runtime
    #
    container.runtime.start()

    #
    # Start observers
    #
    observer_manager.start()

    try:
        yield

    finally:

        #
        # Stop runtime first
        #
        container.runtime.stop()

        #
        # Stop observers
        #
        observer_manager.stop()

        try:
            from .tools_browser import shutdown_browser
            shutdown_browser()

        except Exception as e:
            log.warning(
                "Browser shutdown error: %s",
                e,
            )

        log.info("MYRAA stopped.")



app = FastAPI(
    title="MYRAA Desktop Control Agent",
    version=__version__,
    description="JARVIS-style desktop automation backend for MYRAA.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ExecuteRequest(BaseModel):
    tool: str
    args: Dict[str, Any] = {}

class BrainRequest(BaseModel):
    text: str
    context: Dict[str, Any] = {}


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
        except ImportError:
            pass
        return stats

@app.get("/brain/debug/working-memory")
def working_memory():
    return asdict(
        BRAIN.brain_engine.working_snapshot()
    )

@app.get("/brain/debug/reflections")
def debug_reflections():

    print(id(BRAIN.brain_engine.reflection))

    print(BRAIN.brain_engine.reflection.recent())

    from dataclasses import asdict

    return [
        asdict(x)
        for x in BRAIN.brain_engine.reflection.recent()
    ]

@app.get("/health")
def health() -> Dict[str, Any]:
    return HealthMonitor.get_stats()


@app.get("/tools")
def list_tools() -> Dict[str, Any]:
    return {"tools": sorted(TOOLS.keys()), "count": len(TOOLS)}


class CommandDispatcher:
    @staticmethod
    def dispatch(req: ExecuteRequest) -> ExecuteResponse:
        import time
        from .registry import ValidationLayer, PermissionManager, RecoveryManager, ResponseFormatter, TOOL_SCHEMAS, STATE
        start_time = time.time()
        tool = req.tool
        args = req.args or {}
        log.info("EXEC tool=%s args=%s", tool, _short_args(args))

        if tool not in TOOLS:
            known = ", ".join(sorted(TOOLS.keys()))
            duration = (time.time() - start_time) * 1000
            fmt = ResponseFormatter.error(tool, f"Unknown tool '{tool}'. Known tools: {known}", duration)
            return ExecuteResponse(**fmt)

        handler = TOOLS[tool]
        schema = TOOL_SCHEMAS.get(tool)
        
        try:
            # 1. Validation
            valid_args = ValidationLayer.validate(args, schema)
            # 2. Permissions
            PermissionManager.check(tool, valid_args)
            # 3. Execution
            out = handler(valid_args)
            
            result_text = str(out.get("result", out)) if isinstance(out, dict) else str(out)
            log.info("DONE tool=%s -> %s", tool, result_text[:160])
            
            duration = (time.time() - start_time) * 1000
            fmt = ResponseFormatter.success(tool, out, duration)
            return ExecuteResponse(**fmt)
            
        except ToolError as e:
            log.warning("ToolError in %s: %s", tool, e.message)
            RecoveryManager.handle_failure(tool, e, STATE)
            duration = (time.time() - start_time) * 1000
            fmt = ResponseFormatter.error(tool, e.message, duration)
            return ExecuteResponse(**fmt)
            
        except Exception as e:
            log.error("Unhandled error in %s: %s\n%s", tool, e, traceback.format_exc())
            RecoveryManager.handle_failure(tool, e, STATE)
            duration = (time.time() - start_time) * 1000
            fmt = ResponseFormatter.error(tool, f"Internal error in {tool}: {e}", duration)
            return ExecuteResponse(**fmt)

# ==========================================================
# Initialize Brain
# ==========================================================

dispatcher = CommandDispatcher()

container = ApplicationContainer(
    dispatcher=dispatcher
)

execution_brain = container.execution_brain

BRAIN = Brain(
    dispatcher,
    brain_engine=container.brain_engine,
    orchestrator=container.orchestrator,
)

BRAIN.brain_engine.register_execution_events()

log.info("MYRAA Brain initialized successfully.")

# ==========================================================
# Observer Bootstrap
# ==========================================================

portfolio = PortfolioManager()

provider = ProviderManager()

provider.register(
    "yahoo",
    YahooProvider(),
)

provider.use("yahoo")

finance_service = FinanceService(
    portfolio=portfolio,
    provider=provider,
)

registry = ObserverRegistry()

registry.register(
    "stock_observer",
    StockObserver(finance_service),
)

observer_manager = ObserverManager(
    registry=registry,
    event_handler=BRAIN.brain_engine.process_event,
    poll_interval=30,
)

@app.post("/execute")
def execute(req: ExecuteRequest):

    return execution_brain.execute(req)

@app.post("/brain", response_model=BrainResponse)
def brain(req: BrainRequest):

    try:

        context = BrainContext()

        for key, value in req.context.items():

            if hasattr(context, key):
                setattr(context, key, value)

        result = BRAIN.run(
            text=req.text,
            context=context,
        )

        from dataclasses import asdict, is_dataclass

        if is_dataclass(result):

            brain_result = asdict(result)

        elif isinstance(result, dict):

            brain_result = result.copy()

        else:

            brain_result = {
                "result": str(result),
            }

        brain_result.setdefault("metadata", {})

        brain_result["metadata"].update(
            {
                "brain": "MYRAA",
                "provider": getattr(result, "provider", "unknown"),
                "version": "MCE v2",
            }
        )

        return BrainResponse(
            ok=result.success,
            result=brain_result,
        )
    
    except Exception as e:

        log.exception("Brain execution failed")

        return BrainResponse(
            ok=False,
            error=str(e),
        )

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
