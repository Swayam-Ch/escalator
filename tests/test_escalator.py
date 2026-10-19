import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bench"))

from escalator.agent import Escalator, Reply  # noqa: E402
from escalator.decider import Decider, ServerUnavailable  # noqa: E402
from escalator.patterns import AdequacyGate, GatePolicy, TierRouter  # noqa: E402
from escalator.pricing import cost_usd  # noqa: E402

SMALL, LARGE = "us.amazon.nova-micro-v1:0", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"


class FakeDecider:
    """Answers in the server's wire format from a fixed script; records every state."""

    def __init__(self, route=("small", 0.95), answers=0.97, hedging=0.05, high_stakes=0.05, quality=2.7):
        self.route, self.answers, self.hedging, self.high_stakes, self.quality = (
            route, answers, hedging, high_stakes, quality)
        self.states: list[str] = []
        self.last_latency_ms = 100.0

    def ask(self, state, questions):
        self.states.append(state)
        if "tier" in questions:
            picked, conf = self.route
            others = [o for o in questions["tier"]["criteria"] if o != picked]
            probs = {picked: conf, **{o: (1 - conf) / len(others) for o in others}}
            return {"tier": {"type": "choice", "choice": picked, "probabilities": probs, "confidence": conf}}
        return {
            "answers": {"type": "noul", "noul": self.answers},
            "hedging": {"type": "noul", "noul": self.hedging},
            "high_stakes": {"type": "noul", "noul": self.high_stakes},
            "quality": {"type": "score", "score": self.quality, "legend": {}, "probabilities": {}, "confidence": 0.8},
        }


class FakeModels:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def __call__(self, model_id, system_prompt, prompt):
        self.calls.append((model_id, system_prompt))
        return Reply(model_id, f"answer from {model_id}", 100, 50, 300.0 if model_id == SMALL else 2000.0)


def make(decider, models):
    return Escalator(TierRouter(decider), AdequacyGate(decider), call=models,
                     small_model=SMALL, large_model=LARGE)


# ----------------------------------------------------------------------------- router


@pytest.mark.parametrize("route,expected", [
    (("small", 0.95), "small"),
    (("small", 0.40), "small"),
    (("large", 0.95), "large"),
    (("large", 0.60), "small"),     # unsure -> cheap draft + gate, not a costly guess
    (("clarify", 0.92), "clarify"),
    (("clarify", 0.70), "small"),
])
def test_router_only_acts_on_confident_answers(route, expected):
    assert TierRouter(FakeDecider(route=route)).route("q").action == expected


# ----------------------------------------------------------------------------- gate


@pytest.mark.parametrize("overrides,action,reason", [
    ({}, "accept", "good enough"),
    ({"high_stakes": 0.8}, "escalate", "high-stakes"),
    ({"answers": 0.6}, "escalate", "does not fully answer"),
    ({"hedging": 0.7}, "escalate", "hedging"),
    ({"quality": 1.4}, "escalate", "quality"),
])
def test_gate_policy(overrides, action, reason):
    verdict = AdequacyGate(FakeDecider(**overrides)).check("q", "draft")
    assert verdict.action == action
    assert reason in verdict.reason


def test_gate_policy_is_tunable():
    strict = AdequacyGate(FakeDecider(quality=2.5), GatePolicy(min_quality=2.8))
    assert strict.check("q", "draft").action == "escalate"


def test_gate_sees_request_and_draft():
    decider = FakeDecider()
    AdequacyGate(decider).check("what is 2+2?", "5")
    assert "what is 2+2?" in decider.states[0] and "5" in decider.states[0]


# ----------------------------------------------------------------------------- escalator


def test_accepted_draft_never_touches_large_model():
    models = FakeModels()
    outcome = make(FakeDecider(), models)("capital of France?")
    assert [m for m, _ in models.calls] == [SMALL]
    assert outcome.path == "direct-small" and outcome.final_model == SMALL
    assert outcome.latency_ms == pytest.approx(300 + 100 + 100)


def test_rejected_draft_escalates():
    models = FakeModels()
    outcome = make(FakeDecider(answers=0.3), models)("prove sqrt 2 irrational")
    assert [m for m, _ in models.calls] == [SMALL, LARGE]
    assert outcome.path == "escalated" and outcome.answer == f"answer from {LARGE}"
    assert outcome.cost_usd == pytest.approx(cost_usd(SMALL, 100, 50) + cost_usd(LARGE, 100, 50))


def test_confident_large_skips_draft_and_gate():
    models = FakeModels()
    outcome = make(FakeDecider(route=("large", 0.95)), models)("design a schema")
    assert [m for m, _ in models.calls] == [LARGE]
    assert outcome.gate is None and outcome.path == "direct-large"


def test_clarify_asks_a_question_with_small_model():
    models = FakeModels()
    outcome = make(FakeDecider(route=("clarify", 0.95)), models)("can you fix it?")
    assert models.calls == [(SMALL, models.calls[0][1])] and "clarifying" in models.calls[0][1]
    assert outcome.path == "clarify"


# ----------------------------------------------------------------------------- pricing + client


def test_cost_math():
    assert cost_usd(LARGE, 1_000_000, 1_000_000) == pytest.approx(18.0)
    with pytest.raises(KeyError):
        cost_usd("unknown-model", 1, 1)


def test_client_sends_the_server_wire_format():
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            seen["path"] = self.path
            seen["body"] = json.loads(self.rfile.read(int(self.headers["content-length"])))
            body = json.dumps({"model": "m", "answers": {"x": {"type": "noul", "noul": 0.9}},
                               "usage": {"input_tokens": 5, "output_tokens": 1}, "latency_ms": 42.0}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        decider = Decider(f"http://127.0.0.1:{server.server_port}")
        answers = decider.ask("state", {"x": {"type": "noul", "instructions": "?"}})
    finally:
        server.shutdown()
    assert seen["path"] == "/v1/systemone"
    assert seen["body"]["state"] == "state" and "x" in seen["body"]["questions"]
    assert answers["x"]["noul"] == 0.9 and decider.last_latency_ms == 42.0


def test_client_explains_how_to_start_the_server():
    with pytest.raises(ServerUnavailable, match="strands-decider serve"):
        Decider("http://127.0.0.1:9", timeout=1).ask("s", {})


# ----------------------------------------------------------------------------- bench summary


def test_bench_summary_renders():
    from run_bench import summarise

    rows = [
        {"id": "easy-01", "kind": "easy", "prompt": "p", "path": "direct-small", "baseline_cost": 0.004,
         "escalator_cost": 0.0001, "baseline_ms": 2000, "escalator_ms": 500, "decider_ms": 200, "judge_pass": True},
        {"id": "hard-01", "kind": "hard", "prompt": "q", "path": "escalated", "baseline_cost": 0.01,
         "escalator_cost": 0.0102, "baseline_ms": 6000, "escalator_ms": 6800, "decider_ms": 250, "judge_pass": None},
    ]
    text = summarise(rows)
    assert "$0.0140" in text and "1/1 small-model answers" in text
