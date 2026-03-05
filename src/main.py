from __future__ import annotations

import json
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from .models import (
    InteractiveCancelRequest,
    InteractiveContinueRequest,
    InteractiveRunResponse,
    LiveRunCancelRequest,
    LiveRunStartResponse,
    RunRequest,
    RunResponse,
)
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


@app.post("/run/live/start", response_model=LiveRunStartResponse)
def run_forge_live_start(request: RunRequest) -> LiveRunStartResponse:
    """Start a background quick run for live status streaming.

    What:
        Spawns a live session and returns its session ID.
    Why:
        Lets clients subscribe to incremental activity updates while run is in progress.
    """
    try:
        session_id = orchestrator.start_live_run(request)
        return LiveRunStartResponse(status="started", session_id=session_id)
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"FORGE live start failed: {str(error)}") from error


@app.get("/run/live/stream/{session_id}")
def run_forge_live_stream(session_id: str) -> StreamingResponse:
    """Stream live run events using Server-Sent Events (SSE).

    What:
        Emits `log`, `done`, or `error` events for the requested live session.
    Why:
        Enables low-overhead real-time status UX without polling.
    """

    def event_stream():
        cursor = 0
        while True:
            try:
                snapshot = orchestrator.get_live_snapshot(session_id)
            except Exception as error:
                payload = json.dumps({"message": str(error)})
                yield f"event: error\ndata: {payload}\n\n"
                break

            events = snapshot.get("events", [])
            while cursor < len(events):
                payload = json.dumps(events[cursor])
                yield f"event: log\ndata: {payload}\n\n"
                cursor += 1

            if snapshot.get("done"):
                if snapshot.get("error"):
                    payload = json.dumps({"message": snapshot["error"]})
                    yield f"event: error\ndata: {payload}\n\n"
                else:
                    payload = json.dumps(snapshot.get("result") or {})
                    yield f"event: done\ndata: {payload}\n\n"
                break

            time.sleep(0.25)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/run/live/cancel")
def run_forge_live_cancel(request: LiveRunCancelRequest) -> dict:
    """Cancel a live quick-run session.

    What:
        Sets cancellation flag for the given live session.
    Why:
        Gives users explicit interrupt control during streaming quick runs.
    """
    orchestrator.cancel_live_run(request.session_id)
    return {"status": "cancelled", "session_id": request.session_id}


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
