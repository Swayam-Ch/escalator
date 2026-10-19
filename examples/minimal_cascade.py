"""The confidence-gated cascade with no Strands, no Bedrock and no AWS account.

Only a running decider is needed:

    strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8099
    python examples/minimal_cascade.py

Swap `cheap_llm` and `expensive_llm` for any two callables: OpenAI, Ollama, a local model,
a human queue. The pattern only needs `TierRouter`, `AdequacyGate` and something that answers
decider questions.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from escalator.decider import Decider  # noqa: E402
from escalator.patterns import ACCEPT, CLARIFY, LARGE, AdequacyGate, TierRouter  # noqa: E402


def cheap_llm(prompt: str) -> str:
    # Stand-in for a small model. It knows one fact, and guesses at everything else.
    if "capital of France" in prompt:
        return "Paris."
    return "I think it's probably 42, but I'm not sure."


def expensive_llm(prompt: str) -> str:
    return f"(a careful expert answer to: {prompt})"


def answer(prompt: str, router: TierRouter, gate: AdequacyGate) -> str:
    route = router.route(prompt)
    print(f"  route: {route.action:<8} {route.reason}")
    if route.action == CLARIFY:
        return "Could you tell me a bit more about what you need?"
    if route.action == LARGE:
        return expensive_llm(prompt)

    draft = cheap_llm(prompt)
    verdict = gate.check(prompt, draft)
    print(f"  gate:  {verdict.action:<8} {verdict.reason}  {verdict.signals}")
    return draft if verdict.action == ACCEPT else expensive_llm(prompt)


def main() -> int:
    decider = Decider()
    router, gate = TierRouter(decider), AdequacyGate(decider)
    for prompt in [
        "What is the capital of France?",
        "How many prime numbers are there below 1,000?",
        "Can you fix it?",
    ]:
        print(f"\n> {prompt}")
        print(f"  answer: {answer(prompt, router, gate)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
