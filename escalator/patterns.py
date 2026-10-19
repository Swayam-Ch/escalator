"""The reusable Decider 2B decision pattern: a confidence-gated model cascade.

Two decisions, each a single decider round trip, each turned into an action by plain
Python over calibrated numbers:

    TierRouter    -- before any LLM runs: small model, large model, or ask the user?
    AdequacyGate  -- after the small model drafts: ship the draft, or escalate?

Nothing here imports Strands or Bedrock. Drop this file and `decider.py` into any agent:
the router and gate only need something with an `ask(state, questions)` method.

The decider is calibrated: on unseen short classification tasks, answers at confidence
>= 0.9 are right about 95% of the time (strands-decider evaluation/results.md). So the
policy below only *acts* on a confident answer and otherwise falls back to the safe,
cheap-then-check path. The thresholds are knobs owned by your code, not the model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .decider import Asks, choice, noul, score

# ----------------------------------------------------------------------------- verdicts


@dataclass(frozen=True)
class Verdict:
    """What a decision step concluded, why, and the raw numbers it branched on."""

    action: str
    reason: str
    signals: dict[str, float] = field(default_factory=dict)
    latency_ms: float | None = None


# ----------------------------------------------------------------------------- decision 1


SMALL, LARGE, CLARIFY = "small", "large", "clarify"

ROUTE_QUESTION = choice(
    "Which assistant should handle this user request?",
    {
        SMALL: "a fast, inexpensive model: everyday facts, definitions, short rewrites, "
        "simple how-to, casual conversation",
        LARGE: "a slower expert model: multi-step reasoning, math, writing or debugging "
        "code, careful analysis, or advice where a mistake would be costly",
        CLARIFY: "neither yet: the request is too vague or is missing information needed "
        "to answer it, so the user should be asked a clarifying question",
    },
)


@dataclass
class TierRouter:
    """Pick a tier before spending any LLM tokens.

    Only a confident LARGE or CLARIFY changes the default. Everything else goes to the
    small model, whose draft the AdequacyGate then checks -- so a wrong "small" costs one
    cheap draft, never a bad answer.
    """

    decider: Asks
    sure: float = 0.9

    def route(self, prompt: str) -> Verdict:
        answer = self.decider.ask(f"User request:\n{prompt}", {"tier": ROUTE_QUESTION})["tier"]
        picked, confidence = answer["choice"], answer["confidence"]
        signals = {f"p_{k}": round(v, 3) for k, v in answer["probabilities"].items()}
        signals["confidence"] = round(confidence, 3)
        latency = self.decider.last_latency_ms

        if picked == LARGE and confidence >= self.sure:
            return Verdict(LARGE, "confidently needs the expert model", signals, latency)
        if picked == CLARIFY and confidence >= self.sure:
            return Verdict(CLARIFY, "confidently missing information", signals, latency)
        if picked == SMALL:
            return Verdict(SMALL, "simple request; small model drafts, gate checks", signals, latency)
        return Verdict(SMALL, f"unsure ({picked} @ {confidence:.2f}); try small, gate checks",
                       signals, latency)


# ----------------------------------------------------------------------------- decision 2


ACCEPT, ESCALATE = "accept", "escalate"

QUALITY_LEVELS = [
    "wrong, off-topic, or a refusal",
    "partly right but missing important parts or containing an error",
    "correct but thin; an expert would add something important",
    "correct, complete and clear",
]

GATE_QUESTIONS = {
    "answers": noul(
        "Does the draft directly and fully answer what the user asked?",
        true="the draft addresses every part of the request",
        false="the draft dodges, refuses, misreads, or skips part of the request",
    ),
    "hedging": noul(
        "Does the draft hedge, express uncertainty, or admit it may be wrong?",
        true="the draft says it is unsure, guesses, or tells the user to verify elsewhere",
        false="the draft states its answer plainly",
    ),
    "high_stakes": noul(
        "Could acting on a wrong answer to this request cause real harm (health, legal, "
        "money, security, or broken production code)?",
        true="a mistake here would be costly to the user",
        false="a mistake here would be harmless or easy to notice",
    ),
    "quality": score("How good is the draft as an answer to the request?", QUALITY_LEVELS),
}


@dataclass
class GatePolicy:
    """The knobs. Raise `min_answers` / `min_quality` to escalate more."""

    min_answers: float = 0.9      # P(fully answers) needed to ship the draft
    max_hedging: float = 0.5      # P(hedging) above which the draft is not trusted
    max_high_stakes: float = 0.5  # P(high stakes) above which only the large model answers
    min_quality: float = 2.0      # expected rubric level (0..3) needed to ship


@dataclass
class AdequacyGate:
    """Decide whether a small-model draft is good enough to send to the user."""

    decider: Asks
    policy: GatePolicy = field(default_factory=GatePolicy)

    def check(self, prompt: str, draft: str) -> Verdict:
        state = f"--- USER REQUEST ---\n{prompt}\n\n--- DRAFT ANSWER ---\n{draft}"
        a = self.decider.ask(state, GATE_QUESTIONS)
        signals = {
            "answers": round(a["answers"]["noul"], 3),
            "hedging": round(a["hedging"]["noul"], 3),
            "high_stakes": round(a["high_stakes"]["noul"], 3),
            "quality": round(a["quality"]["score"], 3),
        }
        latency = self.decider.last_latency_ms
        p = self.policy

        # First matching rule wins; each maps one pattern of numbers to one action.
        if signals["high_stakes"] > p.max_high_stakes:
            return Verdict(ESCALATE, "high-stakes request", signals, latency)
        if signals["answers"] < p.min_answers:
            return Verdict(ESCALATE, "draft does not fully answer", signals, latency)
        if signals["hedging"] > p.max_hedging:
            return Verdict(ESCALATE, "draft is hedging", signals, latency)
        if signals["quality"] < p.min_quality:
            return Verdict(ESCALATE, "draft quality below bar", signals, latency)
        return Verdict(ACCEPT, "draft is good enough", signals, latency)
