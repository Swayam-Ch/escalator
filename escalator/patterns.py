"""The reusable Decider 2B decision pattern: a confidence-gated model cascade.

Two decisions, each a single decider round trip, each turned into an action by plain
Python over calibrated numbers:

    TierRouter    -- before any LLM runs: small model, large model, or ask the user?
    AdequacyGate  -- after the small model drafts: ship the draft, or escalate?

Nothing here imports Strands or Bedrock. Drop this file and `decider.py` into any agent:
the router and gate only need something with an `ask(state, questions)` method.

The decider is calibrated: on unseen short classification tasks, answers at confidence
>= 0.9 are right about 95% of the time (strands-decider evaluation/results.md). The router
reads P(large) directly rather than waiting for a confident pick: on our benchmark every
hard request scored P(large) 0.76-0.90 and every easy one 0.17-0.47, while the gate's scores
barely separated correct from incorrect code and maths. The thresholds are knobs owned by
your code, not the model; `bench/sweep.py` replays a benchmark run to choose them.
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

# Strict mode (v3), off by default. Asked in the same decider call as the tier choice, it sends
# code, calculations and professional advice straight to the large model. On a second held-out
# set it cut the saving from 36% to 11% without catching a single extra bad answer, so use it
# only where one wrong answer of that kind costs more than the savings.
STRICT_EXPERT_AT = 0.5

EXPERT_QUESTION = noul(
    "Does this request ask for code to be written or debugged, a multi-step calculation, or "
    "advice on tax, law, medicine or money?",
    true="it asks for code, a calculation with several steps, or professional advice",
    false="it asks for a fact, a definition, a simple conversion, a rewrite or casual help",
)


@dataclass
class TierRouter:
    """Pick a tier before spending any LLM tokens.

    A confident CLARIFY asks the user first. A high enough P(large) skips the cheap draft, and
    so does a request for code, calculation or professional advice in strict mode. Everything
    else goes to the small model, whose draft the AdequacyGate then checks.
    """

    decider: Asks
    sure: float = 0.9                 # confidence needed to act on a CLARIFY pick
    large_at: float = 0.82            # P(large) at or above which the large model answers directly
    expert_at: float | None = None    # strict mode: P(expert request) that does the same

    def route(self, prompt: str) -> Verdict:
        questions = {"tier": ROUTE_QUESTION}
        if self.expert_at is not None:
            questions["expert"] = EXPERT_QUESTION
        answers = self.decider.ask(f"User request:\n{prompt}", questions)
        answer = answers["tier"]
        picked, confidence = answer["choice"], answer["confidence"]
        p_large = answer["probabilities"].get(LARGE, 0.0)
        signals = {f"p_{k}": round(v, 3) for k, v in answer["probabilities"].items()}
        signals["confidence"] = round(confidence, 3)
        p_expert = answers["expert"]["noul"] if "expert" in answers else None
        if p_expert is not None:
            signals["p_expert"] = round(p_expert, 3)
        latency = self.decider.last_latency_ms

        if picked == CLARIFY and confidence >= self.sure:
            return Verdict(CLARIFY, "confidently missing information", signals, latency)
        if p_large >= self.large_at:
            return Verdict(LARGE, f"P(large) {p_large:.2f} >= {self.large_at}", signals, latency)
        if p_expert is not None and p_expert >= self.expert_at:
            return Verdict(LARGE, f"code, calculation or advice (P {p_expert:.2f})", signals, latency)
        return Verdict(SMALL, f"P(large) {p_large:.2f} < {self.large_at}; small drafts, gate checks",
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
