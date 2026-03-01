from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from .models import RunRequest, RunResponse
from .services.orchestrator import ForgeOrchestrator


load_dotenv()

app = FastAPI(title="FORGE Prototype", version="0.1.0")
orchestrator = ForgeOrchestrator()
UI_INDEX = Path(__file__).parent / "ui" / "index.html"


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "forge-prototype"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(UI_INDEX)


@app.post("/run", response_model=RunResponse)
def run_forge(request: RunRequest) -> RunResponse:
    try:
        return orchestrator.run(request)
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"FORGE run failed: {str(error)}") from error


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("src.main:app", host="0.0.0.0", port=port, reload=True)
