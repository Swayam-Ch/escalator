"""Interactive demo: ask questions, watch each decision the decider makes."""

from __future__ import annotations

import argparse
import sys

from .agent import Escalator, Outcome
from .decider import Decider, ServerUnavailable
from .patterns import STRICT_EXPERT_AT, AdequacyGate, TierRouter
from .tools import make_run_python

DIM, BOLD, GREEN, YELLOW, CYAN, RESET = "\033[2m", "\033[1m", "\033[32m", "\033[33m", "\033[36m", "\033[0m"


def short(model_id: str) -> str:
    return model_id.split(".")[-1].split(":")[0]


def render_runs(runs: list[dict]) -> str:
    """The code the model ran through run_python, and what it printed."""
    lines = []
    for i, run in enumerate(runs, 1):
        lines.append(f"{CYAN}run_python #{i}{RESET} {DIM}(AWS Lambda){RESET}")
        lines += [f"  {line}" for line in run["code"].strip().splitlines()]
        output = (run["result"].get("stdout") or run["result"].get("stderr") or "").strip()
        first, *rest = (output or "(nothing printed)").splitlines()
        lines.append(f"  {GREEN}-> {first}{RESET}")
        lines += [f"     {GREEN}{line}{RESET}" for line in rest]
    return "\n".join(lines)


def render(outcome: Outcome, runs: list[dict] | None = None) -> str:
    r = outcome.route
    lines = [f"{CYAN}decider route{RESET}  -> {BOLD}{r.action}{RESET}  ({r.reason})  "
             f"{DIM}{r.signals} {r.latency_ms or 0:.0f}ms{RESET}"]
    if outcome.gate:
        g = outcome.gate
        colour = GREEN if g.action == "accept" else YELLOW
        lines.append(f"{CYAN}decider gate{RESET}   -> {colour}{BOLD}{g.action}{RESET}  ({g.reason})  "
                     f"{DIM}{g.signals} {g.latency_ms or 0:.0f}ms{RESET}")
    for reply in outcome.replies:
        ran = f", ran code {reply.tool_calls}x" if reply.tool_calls else ""
        lines.append(f"{DIM}  {short(reply.model_id)}: {reply.input_tokens}+{reply.output_tokens} tok, "
                     f"${reply.cost_usd:.6f}, {reply.latency_ms:.0f}ms{ran}{RESET}")
    if runs:
        lines.append(render_runs(runs))
    lines.append(f"\n{BOLD}[{short(outcome.final_model)}]{RESET} {outcome.answer}\n")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", nargs="*", help="ask once and exit; omit for a REPL")
    parser.add_argument("--sure", type=float, default=TierRouter.sure, help="confidence needed to ask the user to clarify")
    parser.add_argument("--large-at", type=float, default=TierRouter.large_at, help="P(large) that skips the small draft")
    parser.add_argument("--strict", action="store_true", help="send code, calculations and advice to the large model")
    parser.add_argument("--tool", action="store_true", help="give the answering models the run_python tool (AWS Lambda)")
    args = parser.parse_args()

    decider = Decider()
    try:
        health = decider.health()
    except ServerUnavailable as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"{DIM}decider: {health.get('checkpoint', '?')} on {health.get('device', '?')}{RESET}")

    runs: list[dict] = []
    escalator = Escalator(TierRouter(decider, sure=args.sure, large_at=args.large_at,
                                     expert_at=STRICT_EXPERT_AT if args.strict else None), AdequacyGate(decider),
                          tools=[make_run_python(log=runs)] if args.tool else [])
    if args.prompt:
        print(render(escalator(" ".join(args.prompt)), runs))
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
        runs.clear()
        outcome = escalator(prompt)
        total += outcome.cost_usd
        print(render(outcome, runs))
        print(f"{DIM}session LLM spend: ${total:.6f}{RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
