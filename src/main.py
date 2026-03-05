from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from .models import InteractiveCancelRequest, InteractiveContinueRequest, InteractiveRunResponse, RunRequest, RunResponse
from .services.orchestrator import ForgeOrchestrator


load_dotenv()

app = FastAPI(title="FORGE Prototype", version="0.1.0")
orchestrator = ForgeOrchestrator()
UI_INDEX = Path(__file__).parent / "ui" / "index.html"


@app.get("/health")
def health() -> dict:
    """Return a lightweight liveness payload for probes and quick checks.

    Why: Allows local/dev orchestration and deployment systems to verify the API process
    is up without invoking any model-dependent flow.
    """
    return {"status": "ok", "service": "forge-prototype"}


@app.get("/")
def index() -> FileResponse:
    """Serve the built-in static UI entry page.

    Why: Keeps demo usage simple by hosting both API and UI from one process.
    """
    return FileResponse(UI_INDEX)


@app.post("/run", response_model=RunResponse)
def run_forge(request: RunRequest) -> RunResponse:
    """Execute a full autonomous FORGE run in one request/response cycle.

    Why: Provides a single endpoint for quick mode and API consumers that do not
    need guided human-in-the-loop checkpoints.
    """
    try:
        return orchestrator.run(request)
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"FORGE run failed: {str(error)}") from error


@app.post("/run/interactive/start", response_model=InteractiveRunResponse)
def run_interactive_start(request: RunRequest) -> InteractiveRunResponse:
    """Start a guided run session and return either a question or final result.

    Why: Guided mode is stateful and may require multiple user replies before execution.
    """
    try:
        return orchestrator.start_interactive(request)
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"FORGE interactive start failed: {str(error)}") from error


@app.post("/run/interactive/continue", response_model=InteractiveRunResponse)
def run_interactive_continue(request: InteractiveContinueRequest) -> InteractiveRunResponse:
    """Continue a guided run session with user input or a skip signal.

    Why: Separates session progression from initialization and preserves clear API semantics.
    """
    try:
        return orchestrator.continue_interactive(
            session_id=request.session_id,
            user_comment=request.user_comment,
            skip=request.skip,
        )
    except Exception as error:
        status_code = 404 if "not found" in str(error).lower() else 503
        raise HTTPException(status_code=status_code, detail=f"FORGE interactive continue failed: {str(error)}") from error


@app.post("/run/interactive/cancel")
def run_interactive_cancel(request: InteractiveCancelRequest) -> dict:
    """Cancel and remove an active guided session.

    Why: Lets users safely interrupt long or no-longer-relevant guided runs.
    """
    orchestrator.cancel_interactive(request.session_id)
    return {"status": "cancelled", "session_id": request.session_id}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("src.main:app", host="0.0.0.0", port=port, reload=True)
