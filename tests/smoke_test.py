from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from src.main import app


def run_smoke_test() -> int:
    client = TestClient(app)

    tests = []

    health = client.get("/health")
    health_ok = health.status_code == 200 and health.json().get("status") == "ok"
    tests.append(
        {
            "name": "health",
            "status": health.status_code,
            "ok": health_ok,
            "detail": health.json() if health.headers.get("content-type", "").startswith("application/json") else health.text,
        }
    )

    scenarios = [
        {
            "name": "roadmap_basic",
            "payload": {
                "goal": "Create a 4-week launch roadmap for a student app",
                "constraints": ["Weekly milestones", "Show assumptions", "Concise output"],
                "config": {
                    "strategy_threshold": 0.7,
                    "quality_threshold": 0.75,
                    "max_iterations": 1,
                    "output_format": "markdown",
                },
            },
        },
        {
            "name": "research_plan",
            "payload": {
                "goal": "Plan a literature review workflow for AI agent safety research",
                "constraints": ["Include task ownership", "Include risks and mitigations", "Mention unknowns"],
                "config": {
                    "strategy_threshold": 0.8,
                    "quality_threshold": 0.8,
                    "max_iterations": 2,
                    "output_format": "markdown",
                },
            },
        },
    ]

    for case in scenarios:
        response = client.post("/run", json=case["payload"])
        ok = response.status_code == 200
        body = response.json() if ok else {"error": response.text}

        tests.append(
            {
                "name": case["name"],
                "status": response.status_code,
                "ok": ok,
                "ended_reason": body.get("ended_reason") if ok else None,
                "iterations": body.get("iterations") if ok else None,
                "confidence_trace": body.get("confidence_trace") if ok else None,
                "quality_trace": body.get("quality_trace") if ok else None,
                "activity_events": len(body.get("activity_log", [])) if ok else None,
                "output_preview": (body.get("final_output", "")[:180].replace("\n", " ") if ok else body.get("error", "")[:180]),
            }
        )

    all_ok = True
    for item in tests:
        print("---")
        print(f"TEST: {item['name']}")
        print(f"STATUS: {item['status']}")
        print(f"PASS: {item['ok']}")
        if item["name"] == "health":
            print(f"DETAIL: {item['detail']}")
        else:
            print(f"ENDED: {item.get('ended_reason')}")
            print(f"ITERATIONS: {item.get('iterations')}")
            print(f"CONF: {item.get('confidence_trace')}")
            print(f"QUAL: {item.get('quality_trace')}")
            print(f"ACTIVITY_EVENTS: {item.get('activity_events')}")
            print(f"PREVIEW: {item.get('output_preview')}")

        all_ok = all_ok and bool(item["ok"])

    summary = {"all_ok": all_ok, "tests": tests}
    print("=== SUMMARY ===")
    print(json.dumps(summary, indent=2, default=str))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(run_smoke_test())
