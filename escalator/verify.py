"""Check a cheap answer against the code that produced it, instead of asking a model to judge it.

The 2B gate can tell whether an answer addresses the question, not whether a number is right, so
it escalates almost every calculation (17 of 18 Nova drafts in the benchmark). When the small model
used run_python, there is a better check: ask it twice, and keep its answer only if

  1. grounded: each answer's final number is what its last successful program printed, and
  2. agree:    the two independent runs printed the same result.

Anything else escalates. A failed check costs one large-model call, never a wrong answer kept on
purpose. No dependencies, like patterns.py.
"""

from __future__ import annotations

import re

from .patterns import ACCEPT, ESCALATE, Verdict

NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?")


def numbers(text: str) -> list[float]:
    return [float(n.replace(",", "")) for n in NUMBER.findall(text)]


def parse_result(text: str) -> tuple[bool, str]:
    """(ran cleanly, stdout) from a run_python result, as written by tools.format_result."""
    if not text.startswith("exit code 0") or "stdout:\n" not in text:
        return False, ""
    stdout = text.split("stdout:\n", 1)[1].split("\nstderr:\n", 1)[0]
    return stdout != "(nothing printed)", stdout


def printed_value(tool_results: list[str]) -> float | None:
    """The last number on the last line printed by the last program that ran cleanly."""
    for result in reversed(tool_results):
        ok, stdout = parse_result(result)
        lines = [line for line in stdout.splitlines() if line.strip()]
        if ok and lines:
            found = numbers(lines[-1])
            return found[-1] if found else None
    return None


def answer_value(text: str) -> float | None:
    """The last number in the answer: where the final result usually is."""
    found = numbers(text)
    return found[-1] if found else None


def same(a: float | None, b: float | None) -> bool:
    return a is not None and b is not None and abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def check(first, second) -> Verdict:
    """Accept `first` (a Reply) only if both drafts are grounded in their code and agree."""
    p1, p2 = printed_value(first.tool_results), printed_value(second.tool_results)
    a1, a2 = answer_value(first.text), answer_value(second.text)
    signals = {"printed_1": p1, "printed_2": p2, "answer_1": a1, "answer_2": a2}
    if not (first.tool_calls and second.tool_calls):
        return Verdict(ESCALATE, "no code ran", signals)
    if not (same(a1, p1) and same(a2, p2)):
        return Verdict(ESCALATE, "an answer doesn't match what its code printed", signals)
    if not same(p1, p2):
        return Verdict(ESCALATE, f"two runs disagree ({p1:.15g} vs {p2:.15g})", signals)
    return Verdict(ACCEPT, f"two runs printed {p1:.15g} and the answer matches", signals)
