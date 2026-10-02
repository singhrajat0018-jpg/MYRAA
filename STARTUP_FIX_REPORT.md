# MYRAA DESKTOP AGENT STARTUP FIX REPORT

**Date:** 2026-08-23  
**Status:** PARTIALLY RESOLVED - Import fixed, Lifespan startup still blocking

---

## 1. ROOT CAUSE IDENTIFIED

### Primary Issue: Import-Time Initialization
The Desktop Agent had **45+ second import hang** caused by:

1. **Heavy imports at module level** (`desktop_agent/main.py` lines 18-47)
   - `ApplicationContainer` import alone: **7.0 seconds**
   - `StockObserver` import: **2.8 seconds**
   - `ScreenObserver` import: **0.5 seconds**
   - Total import overhead: **~10 seconds** just from imports

2. **Module-level instantiation** (lines 625-704 in original `main.py`)
   - `ApplicationContainer()` instantiation
   - `Brain()` initialization
   - Finance service setup
   - Observer registry and manager creation
   - All happening **before** FastAPI lifespan even started

3. **Deep import chain bottleneck**
   - `desktop_agent/brain/semantic/providers/gemini_provider.py` line 16: `from google import genai`
   - The Google Generative AI SDK import is extremely slow (15+ seconds)
   - Likely performs HTTP calls, gRPC initialization, proto downloads, SSL setup

### Evidence
```bash
# Before fix:
python -c "import desktop_agent.main"  
# Result: 45+ seconds (timeout)

# Module-level imports timing:
desktop_agent.core.application_container: 6.9972s
desktop_agent.brain.observer.observers.stock_observer: 2.7821s
desktop_agent.brain.observer.observers.screen_observer: 0.5041s
desktop_agent.brain.brain: 0.0726s
```

---

## 2. FIX IMPLEMENTED

### Changes to `desktop_agent/main.py`

#### A. Removed Heavy Module-Level Imports
**Before:**
```python
from .brain.brain import Brain
from desktop_agent.core.application_container import ApplicationContainer
from .brain.execution_brain import ExecutionBrain
from desktop_agent.brain.observer.registry import ObserverRegistry
from desktop_agent.brain.observer.manager import ObserverManager
# ... 15 more heavy imports
```

**After:**
```python
from typing import Any, Dict, List, Optional, TYPE_CHECKING

# Lazy imports for type hints only
if TYPE_CHECKING:
    from .brain.brain import Brain
    from desktop_agent.core.application_container import ApplicationContainer
    from .brain.execution_brain import ExecutionBrain
    from desktop_agent.brain.observer.manager import ObserverManager
```

#### B. Moved Initialization to Lifespan Startup
**Before:**
```python
# Module level (executed at import time)
container = ApplicationContainer(dispatcher=dispatcher)
BRAIN = Brain(...)
portfolio = PortfolioManager()
# ... all initialization at import time
```

**After:**
```python
# Module level (fast)
container = None
BRAIN = None
execution_brain = None
observer_manager = None
dispatcher = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global container, BRAIN, execution_brain, observer_manager, dispatcher
    
    # Lazy imports - only import during startup
    from .brain.brain import Brain
    from desktop_agent.core.application_container import ApplicationContainer
    from desktop_agent.brain.observer.registry import ObserverRegistry
    # ... other imports
    
    # Initialize services
    dispatcher = CommandDispatcher()
    container = ApplicationContainer(dispatcher=dispatcher)
    BRAIN = Brain(...)
    # ... rest of initialization
```

#### C. Removed Duplicate Initialization
The file had duplicate initialization code (lines 706-784) that was left over after adding the lifespan initialization. Removed it.

---

## 3. RESULTS

### Import Performance
**FIXED:** Import time reduced from **45+ seconds to 0.78 seconds** (~98% improvement)

```bash
python -c "import time; t0 = time.time(); import desktop_agent.main; print(f'Import took {time.time() - t0:.2f}s')"
# Result: Import took 0.78s
```

### Module Import Successfully Loads
```bash
python -c "from desktop_agent.main import app; print('App imported successfully:', app)"
# Result: App imported successfully: <fastapi.applications.FastAPI object at 0x...>
```

---

## 4. REMAINING ISSUE: Lifespan Startup Hang

### Current Status: BLOCKED

The Desktop Agent now imports quickly but **hangs during lifespan startup** after the Knowledge Worker starts.

### Evidence from `test_startup.py`
```
[INFO] Loaded 89 desktop tools
[INFO] MYRAA Desktop Control Agent v1.0.0 starting.
[INFO] [Knowledge Worker] Started
[killed after 20+ seconds]
```

### Root Cause
The `ApplicationContainer` initialization (even when deferred to lifespan) triggers:
1. **Background worker threads** that block
2. **Knowledge Worker** (`desktop_agent/brain/knowledge/queue/worker.py`) starts but hangs
3. Likely other workers/observers that are blocking on initialization

### Specific Blocker
The Knowledge Worker thread starts (`threading.Thread(daemon=True)`) and logs "[Knowledge Worker] Started" but then the entire startup hangs. This suggests:
- The worker is waiting on a blocking operation
- Another component initialized by `ApplicationContainer` is blocking
- A deadlock or infinite wait condition

---

## 5. NEXT STEPS TO COMPLETE THE FIX

### Step 1: Identify Blocking Worker
**Action:** Add detailed logging to `ApplicationContainer._build()` to see exactly where it hangs

```python
# In desktop_agent/core/application_container.py
def _build(self):
    log.info("Building Blackboard...")
    self.blackboard = Blackboard()
    log.info("Blackboard built")
    
    log.info("Building ContextManager...")
    self.context_manager = ContextManager()
    log.info("ContextManager built")
    
    # ... log each component
```

### Step 2: Make Background Workers Lazy
**Problem:** Workers start immediately in `__init__`  
**Solution:** Add explicit `.start()` methods, call them after app is ready

```python
# Example for Knowledge Worker
class UnifiedMemoryManager:
    def __init__(self):
        # Don't start worker here
        self._worker = None
    
    def start_worker(self):
        # Start worker explicitly when needed
        if self._worker is None:
            self._worker = KnowledgeWorker(...)
            self._worker.start()
```

### Step 3: Defer Non-Critical Services
Move these to **after** the `/health/ready` endpoint reports HEALTHY:
- Vision pipeline (`container.vision.start()`)
- Observers (`observer_manager.start()`)
- Runtime manager (`container.runtime.start()`)

### Step 4: Add Startup Timeout + Health Checks
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Wrap each initialization with timeout
        async with asyncio.timeout(30):
            container = ApplicationContainer(...)
        
        async with asyncio.timeout(10):
            BRAIN = Brain(...)
        
        # Mark ready
        log.info("MYRAA Desktop Agent READY")
        yield
    except asyncio.TimeoutError:
        log.error("Startup timeout - check ApplicationContainer initialization")
        raise
```

### Step 5: Fix Gemini Provider Lazy Import
Make `google.genai` import lazy inside `GeminiSemanticProvider`:

```python
# desktop_agent/brain/semantic/providers/gemini_provider.py
class GeminiSemanticProvider(BaseSemanticProvider):
    def __init__(self, api_key: str | None = None, model: str = "gemini-3.6-flash"):
        # Don't import here
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            from google import genai  # Lazy import
            self._client = genai.Client(api_key=self.api_key)
        return self._client
```

---

## 6. VERIFICATION CHECKLIST

After implementing the remaining fixes:

- [ ] `python -c "import desktop_agent.main"` completes in < 1 second
- [ ] `python -m uvicorn desktop_agent.main:app --host 127.0.0.1 --port 8765` starts without hanging
- [ ] `curl http://127.0.0.1:8765/health/live` returns `{"status": "ok"}` within 5 seconds
- [ ] `curl http://127.0.0.1:8765/health/ready` returns `{"status": "HEALTHY"}` within 30 seconds
- [ ] `curl http://127.0.0.1:8765/tools` returns the tool list
- [ ] POST to `/execute` with a simple tool (e.g., `systemInfo`) works
- [ ] Node server can connect and call `/brain` successfully
- [ ] start-myraa.bat launcher reports "Desktop Agent ready" within 30 seconds

---

## 7. STARTUP LIFECYCLE (PROPOSED)

```
IMPORT (< 1s)
├─ Load FastAPI, Pydantic, TOOLS registry
├─ Define lifespan, app, routes (definitions only)
└─ NO heavy imports, NO instantiation

LIFESPAN STARTUP (target: < 30s)
├─ Import heavy modules (lazy)
├─ Build ApplicationContainer (no background workers yet)
├─ Initialize Brain (rules/heuristics only, no LLM calls)
├─ Initialize observers (register, don't start polling)
├─ Mark /health/live = OK
├─ Mark /health/ready = HEALTHY
├─ Start background workers (vision, observers, runtime)
└─ Log "MYRAA Desktop Agent READY"

RUNTIME
├─ /execute handles tool calls
├─ /brain handles cognitive processing
├─ Observers poll in background
└─ Vision pipeline runs continuously

SHUTDOWN
├─ Stop vision pipeline
├─ Stop runtime manager
├─ Stop observers
├─ Close browser
└─ Clean exit
```

---

## 8. FILES MODIFIED

1. **`desktop_agent/main.py`**
   - Removed 15+ heavy module-level imports
   - Added TYPE_CHECKING guard for type hints
   - Moved all imports into `lifespan()` function
   - Moved all instantiation into `lifespan()` function
   - Removed duplicate initialization code (lines 706-784)
   - Added null-checks to endpoints that reference BRAIN/container

---

## 9. ARCHITECTURAL LESSONS

### DO NOT
- ❌ Import heavy SDK libraries at module level (`google.genai`, large ML libraries)
- ❌ Instantiate services at module level
- ❌ Start background threads/workers during `__init__`
- ❌ Make blocking HTTP/gRPC calls during import or `__init__`
- ❌ Perform expensive disk I/O during import

### DO
- ✅ Use lazy imports (import inside functions when needed)
- ✅ Use TYPE_CHECKING guard for type hint imports
- ✅ Defer instantiation to FastAPI lifespan startup
- ✅ Add explicit `.start()` methods for background workers
- ✅ Implement health checks (/health/live, /health/ready)
- ✅ Log each startup phase for diagnostics
- ✅ Use timeouts to catch hung initialization
- ✅ Make services start in dependency order

---

## 10. GEMINI VOICE CONFIGURATION ERROR (SEPARATE ISSUE)

Also observed during testing:

```
Close code: 1007
Reason: "No matching speaker voice found for name: Chloe and language:"
```

### Fix Required
Check `server.ts` Gemini Live voice configuration and ensure it uses a supported voice name for the configured model. This is a **separate issue** from the Desktop Agent startup and should be fixed independently.

---

## FINAL STATUS

### ✅ RESOLVED
- Import-time initialization hang (45s → 0.78s)
- Module-level instantiation removed
- Lazy import pattern implemented
- Fast module import verified

### ⚠️ BLOCKED
- Lifespan startup hangs after Knowledge Worker starts
- Port 8765 never becomes ready
- Background worker blocking unidentified

### 🔧 READY FOR NEXT PHASE
The architecture is now correct (lazy imports, deferred initialization). The remaining blocker is in `ApplicationContainer` or one of its workers. With proper logging and worker lifecycle management, this should be straightforward to resolve.

---

## REGRESSION PREVENTION

Add to CI/test suite:
```python
def test_fast_import():
    import time
    t0 = time.time()
    import desktop_agent.main
    elapsed = time.time() - t0
    assert elapsed < 2.0, f"Import took {elapsed:.2f}s (max 2.0s)"

def test_startup_ready():
    # Start uvicorn in subprocess
    # Poll /health/ready with 30s timeout
    # Assert it returns HEALTHY
```

---

**END OF REPORT**
