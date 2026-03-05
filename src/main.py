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
    """Return a lightweight liveness payload.

    What:
        Exposes service status without invoking model or orchestration logic.
    Why:
        Enables health probes and quick diagnostics in local and deployed environments.
    """
    return {"status": "ok", "service": "forge-prototype"}


@app.get("/")
def index() -> FileResponse:
    """Serve the built-in UI entry page.

    What:
        Returns the static `index.html` file for the web interface.
    Why:
        Keeps onboarding simple by hosting API and UI from the same FastAPI process.
    """
    return FileResponse(UI_INDEX)


@app.post("/run", response_model=RunResponse)
def run_forge(request: RunRequest) -> RunResponse:
    """Execute a full autonomous FORGE run.

    What:
        Runs planning, retrieval, execution, and review in one synchronous API call.
    Why:
        Supports quick mode and integrations that do not require guided checkpoints.
    """
    try:
        return orchestrator.run(request)
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"FORGE run failed: {str(error)}") from error


@app.post("/run/interactive/start", response_model=InteractiveRunResponse)
def run_interactive_start(request: RunRequest) -> InteractiveRunResponse:
    """Start a guided run session.

    What:
        Initializes session state and returns either a clarification question or a completed result.
    Why:
        Guided mode requires stateful, multi-step interaction before execution can finalize.
    """
    try:
        return orchestrator.start_interactive(request)
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"FORGE interactive start failed: {str(error)}") from error


@app.post("/run/interactive/continue", response_model=InteractiveRunResponse)
def run_interactive_continue(request: InteractiveContinueRequest) -> InteractiveRunResponse:
    """Continue a guided run session.

    What:
        Applies user feedback (or skip), advances the session, and returns next question or result.
    Why:
        Keeps progression explicit and separates session updates from session creation.
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
    """Cancel an active guided session.

    What:
        Removes the in-memory interactive session by `session_id`.
    Why:
        Gives users deterministic interruption control for long or irrelevant runs.
    """
    orchestrator.cancel_interactive(request.session_id)
    return {"status": "cancelled", "session_id": request.session_id}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("src.main:app", host="0.0.0.0", port=port, reload=True)
