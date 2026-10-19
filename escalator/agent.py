"""Escalator: route -> draft -> gate -> (maybe) escalate, with a full trace of each step."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from .patterns import ACCEPT, CLARIFY, LARGE, AdequacyGate, TierRouter, Verdict
from .pricing import cost_usd

SMALL_MODEL = os.environ.get("ESCALATOR_SMALL_MODEL", "us.amazon.nova-micro-v1:0")
LARGE_MODEL = os.environ.get("ESCALATOR_LARGE_MODEL", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")

SYSTEM_PROMPT = "You are a helpful assistant. Answer accurately and concisely."
CLARIFY_PROMPT = (
    "The user's request is missing information you need. Do not answer it. Ask one short, "
    "specific clarifying question."
)


@dataclass
class Reply:
    """One LLM call: what it said, what it cost, how long it took."""

    model_id: str
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float

    @property
    def cost_usd(self) -> float:
        return cost_usd(self.model_id, self.input_tokens, self.output_tokens)


# (model_id, system_prompt, user_prompt) -> Reply. Swappable so tests need no AWS.
CallModel = Callable[[str, str, str], Reply]


def bedrock_call(model_id: str, system_prompt: str, prompt: str) -> Reply:
    """One stateless Strands agent turn on a Bedrock model."""
    from strands import Agent
    from strands.models import BedrockModel

    model = BedrockModel(model_id=model_id, region_name=os.environ.get("AWS_REGION", "us-east-1"))
    agent = Agent(model=model, system_prompt=system_prompt, callback_handler=None)
    started = time.perf_counter()
    result = agent(prompt)
    usage = result.metrics.accumulated_usage
    return Reply(model_id, str(result).strip(), usage["inputTokens"], usage["outputTokens"],
                 (time.perf_counter() - started) * 1000)


@dataclass
class Outcome:
    answer: str
    final_model: str
    route: Verdict
    gate: Verdict | None = None
    replies: list[Reply] = field(default_factory=list)

    @property
    def cost_usd(self) -> float:
        return sum(r.cost_usd for r in self.replies)

    @property
    def decider_ms(self) -> float:
        return sum(v.latency_ms or 0 for v in (self.route, self.gate) if v)

    @property
    def latency_ms(self) -> float:
        return sum(r.latency_ms for r in self.replies) + self.decider_ms

    @property
    def path(self) -> str:
        """A one-word summary for tables: direct-small, escalated, direct-large, clarify."""
        if self.route.action == CLARIFY:
            return "clarify"
        if self.route.action == LARGE:
            return "direct-large"
        return "direct-small" if self.gate and self.gate.action == ACCEPT else "escalated"


@dataclass
class Escalator:
    router: TierRouter
    gate: AdequacyGate
    call: CallModel = bedrock_call
    small_model: str = SMALL_MODEL
    large_model: str = LARGE_MODEL

    def __call__(self, prompt: str) -> Outcome:
        route = self.router.route(prompt)

        if route.action == CLARIFY:
            reply = self.call(self.small_model, CLARIFY_PROMPT, prompt)
            return Outcome(reply.text, self.small_model, route, replies=[reply])

        if route.action == LARGE:
            reply = self.call(self.large_model, SYSTEM_PROMPT, prompt)
            return Outcome(reply.text, self.large_model, route, replies=[reply])

        draft = self.call(self.small_model, SYSTEM_PROMPT, prompt)
        verdict = self.gate.check(prompt, draft.text)
        if verdict.action == ACCEPT:
            return Outcome(draft.text, self.small_model, route, verdict, [draft])

        final = self.call(self.large_model, SYSTEM_PROMPT, prompt)
        return Outcome(final.text, self.large_model, route, verdict, [draft, final])
