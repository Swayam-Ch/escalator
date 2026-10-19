"""Interactive demo: ask questions, watch each decision the decider makes."""

from __future__ import annotations

import argparse
import sys

from .agent import Escalator, Outcome
from .decider import Decider, ServerUnavailable
from .patterns import STRICT_EXPERT_AT, AdequacyGate, TierRouter

DIM, BOLD, GREEN, YELLOW, CYAN, RESET = "\033[2m", "\033[1m", "\033[32m", "\033[33m", "\033[36m", "\033[0m"


def short(model_id: str) -> str:
    return model_id.split(".")[-1].split(":")[0]


def render(outcome: Outcome) -> str:
    r = outcome.route
    lines = [f"{CYAN}decider route{RESET}  -> {BOLD}{r.action}{RESET}  ({r.reason})  "
             f"{DIM}{r.signals} {r.latency_ms or 0:.0f}ms{RESET}"]
    if outcome.gate:
        g = outcome.gate
        colour = GREEN if g.action == "accept" else YELLOW
        lines.append(f"{CYAN}decider gate{RESET}   -> {colour}{BOLD}{g.action}{RESET}  ({g.reason})  "
                     f"{DIM}{g.signals} {g.latency_ms or 0:.0f}ms{RESET}")
    for reply in outcome.replies:
        lines.append(f"{DIM}  {short(reply.model_id)}: {reply.input_tokens}+{reply.output_tokens} tok, "
                     f"${reply.cost_usd:.6f}, {reply.latency_ms:.0f}ms{RESET}")
    lines.append(f"\n{BOLD}[{short(outcome.final_model)}]{RESET} {outcome.answer}\n")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", nargs="*", help="ask once and exit; omit for a REPL")
    parser.add_argument("--sure", type=float, default=TierRouter.sure, help="confidence needed to ask the user to clarify")
    parser.add_argument("--large-at", type=float, default=TierRouter.large_at, help="P(large) that skips the small draft")
    parser.add_argument("--strict", action="store_true", help="send code, calculations and advice to the large model")
    args = parser.parse_args()

    decider = Decider()
    try:
        health = decider.health()
    except ServerUnavailable as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"{DIM}decider: {health.get('checkpoint', '?')} on {health.get('device', '?')}{RESET}")

    escalator = Escalator(TierRouter(decider, sure=args.sure, large_at=args.large_at,
                                     expert_at=STRICT_EXPERT_AT if args.strict else None), AdequacyGate(decider))
    if args.prompt:
        print(render(escalator(" ".join(args.prompt))))
        return 0

    total = 0.0
    while True:
        try:
            prompt = input(f"{BOLD}you>{RESET} ").strip()
        except EOFError:
            break
        if prompt in {"exit", "quit"}:
            break
        if not prompt:
            continue
        outcome = escalator(prompt)
        total += outcome.cost_usd
        print(render(outcome))
        print(f"{DIM}session LLM spend: ${total:.6f}{RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
