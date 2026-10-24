"""Escalator: route -> draft -> gate -> (maybe) escalate, with a full trace of each step."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from . import verify
from .patterns import ACCEPT, CLARIFY, LARGE, AdequacyGate, TierRouter, Verdict
from .pricing import cost_usd
from .tools import TOOL_HINT, RunBudget

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
    tool_calls: int = 0
    tool_results: list[str] = field(default_factory=list)  # what each tool call returned, in order

    @property
    def cost_usd(self) -> float:
        return cost_usd(self.model_id, self.input_tokens, self.output_tokens)


# (model_id, system_prompt, user_prompt, tools) -> Reply. Swappable so tests need no AWS.
CallModel = Callable[..., Reply]


def bedrock_call(model_id: str, system_prompt: str, prompt: str, tools: list | None = None) -> Reply:
    """One stateless Strands agent turn on a Bedrock model, with any tools it may call."""
    from strands import Agent
    from strands.models import BedrockModel

    model = BedrockModel(model_id=model_id, region_name=os.environ.get("AWS_REGION", "us-east-1"))
    if tools:
        system_prompt = f"{system_prompt}\n\n{TOOL_HINT}"
    agent = Agent(model=model, system_prompt=system_prompt, tools=tools or [], callback_handler=None,
                  hooks=[RunBudget()] if tools else None)
    started = time.perf_counter()
    result = agent(prompt)
    usage = result.metrics.accumulated_usage
    calls = sum(m.call_count for m in result.metrics.tool_metrics.values())
    return Reply(model_id, str(result).strip(), usage["inputTokens"], usage["outputTokens"],
                 (time.perf_counter() - started) * 1000, calls, tool_results(agent.messages))


def tool_results(messages: list[dict]) -> list[str]:
    """The text of every tool result in a Strands conversation, in order."""
    return ["".join(part.get("text", "") for part in block["toolResult"].get("content", []))
            for message in messages for block in message.get("content", []) if "toolResult" in block]


@dataclass
class Outcome:
    answer: str
    final_model: str
    route: Verdict
    gate: Verdict | None = None
    replies: list[Reply] = field(default_factory=list)
    check: Verdict | None = None  # verify mode: the code check on two small-model drafts

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
        """A one-word summary for tables: verified, direct-small, escalated, direct-large, clarify."""
        if self.check:  # verify mode always drafts with the small model first
            if self.check.action == ACCEPT:
                return "verified"
            return "direct-small" if self.gate and self.gate.action == ACCEPT else "escalated"
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
    tools: list = field(default_factory=list)  # e.g. [make_run_python()]; the clarify step gets none
    verify: bool = False  # with tools: two small drafts checked against their code (see verify.py)

    def __call__(self, prompt: str) -> Outcome:
        route = self.router.route(prompt)

        if route.action == CLARIFY:
            reply = self.call(self.small_model, CLARIFY_PROMPT, prompt)
            return Outcome(reply.text, self.small_model, route, replies=[reply])

        if self.verify and self.tools:
            return self._verified(prompt, route)

        if route.action == LARGE:
            reply = self.call(self.large_model, SYSTEM_PROMPT, prompt, self.tools)
            return Outcome(reply.text, self.large_model, route, replies=[reply])

        draft = self.call(self.small_model, SYSTEM_PROMPT, prompt, self.tools)
        verdict = self.gate.check(prompt, draft.text)
        if verdict.action == ACCEPT:
            return Outcome(draft.text, self.small_model, route, verdict, [draft])

        final = self.call(self.large_model, SYSTEM_PROMPT, prompt, self.tools)
        return Outcome(final.text, self.large_model, route, verdict, [draft, final])

    def _verified(self, prompt: str, route: Verdict) -> Outcome:
        """Ask the small model twice, in parallel; keep its answer if the code check passes.

        If neither draft ran code, the question wasn't a calculation, so the usual flow applies
        with the first draft. Otherwise a failed check goes to the large model.
        """
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.map(lambda _: self.call(self.small_model, SYSTEM_PROMPT, prompt, self.tools),
                                     range(2))
        drafts = [first, second]
        check = verify.check(first, second)
        if check.action == ACCEPT:
            return Outcome(first.text, self.small_model, route, replies=drafts, check=check)

        if first.tool_calls or second.tool_calls or route.action == LARGE:
            final = self.call(self.large_model, SYSTEM_PROMPT, prompt, self.tools)
            return Outcome(final.text, self.large_model, route, replies=[*drafts, final], check=check)

        verdict = self.gate.check(prompt, first.text)
        if verdict.action == ACCEPT:
            return Outcome(first.text, self.small_model, route, verdict, drafts, check=check)
        final = self.call(self.large_model, SYSTEM_PROMPT, prompt, self.tools)
        return Outcome(final.text, self.large_model, route, verdict, [*drafts, final], check=check)
