"""A small synchronous client for a running `strands-decider serve` endpoint.

Modelled on the client in strands-labs/strands-decider/examples/strands: plain urllib, so
the reusable pattern in `patterns.py` needs nothing beyond the standard library.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any, Protocol

DEFAULT_URL = os.environ.get("STRANDS_DECIDER_URL", "http://127.0.0.1:8099")
SERVE_HINT = "strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8099"


class ServerUnavailable(RuntimeError):
    """Nothing is answering at the decider URL."""


class Asks(Protocol):
    """Anything that answers decider questions. The HTTP client and the test fakes both fit."""

    last_latency_ms: float | None

    def ask(self, state: Any, questions: Mapping[str, dict[str, Any]]) -> dict[str, Any]: ...


def noul(instructions: str, true: str | None = None, false: str | None = None) -> dict[str, Any]:
    """Yes/no question. The answer's `noul` field is P(yes)."""
    question: dict[str, Any] = {"type": "noul", "instructions": instructions}
    criteria = {k: v for k, v in (("true", true), ("false", false)) if v}
    if criteria:
        question["criteria"] = criteria
    return question


def choice(instructions: str, options: Mapping[str, str]) -> dict[str, Any]:
    """Pick one of N. `options` maps option name -> what it means."""
    return {"type": "choice", "instructions": instructions, "criteria": dict(options)}


def score(instructions: str, levels: list[str]) -> dict[str, Any]:
    """Rate against an ordered rubric, lowest level first."""
    return {"type": "score", "instructions": instructions, "criteria": list(levels)}


class Decider:
    """One state, many typed questions, one round trip."""

    def __init__(self, url: str = DEFAULT_URL, timeout: float = 120.0) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.calls = 0
        self.last_latency_ms: float | None = None

    def ask(self, state: Any, questions: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
        body = json.dumps({"state": state, "questions": dict(questions)}).encode()
        request = urllib.request.Request(
            f"{self.url}/v1/systemone", data=body, headers={"content-type": "application/json"}
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read())
        except urllib.error.URLError as exc:
            raise ServerUnavailable(
                f"no strands-decider at {self.url} ({exc}). Start one with:\n    {SERVE_HINT}"
            ) from exc
        self.calls += 1
        # Prefer the server's own timing; fall back to wall clock including HTTP.
        self.last_latency_ms = payload.get("latency_ms") or (time.perf_counter() - started) * 1000
        return payload["answers"]

    def health(self) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(f"{self.url}/health", timeout=10) as response:
                return json.loads(response.read())
        except urllib.error.URLError as exc:
            raise ServerUnavailable(
                f"no strands-decider at {self.url} ({exc}). Start one with:\n    {SERVE_HINT}"
            ) from exc
