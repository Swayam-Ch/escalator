"""Measure Escalator against "always use the large model" on bench/questions.jsonl.

    python bench/run_bench.py            # cost + latency
    python bench/run_bench.py --judge    # also: large model checks each answer the small model shipped

Writes bench/results/<timestamp>/results.jsonl and summary.md.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from escalator.agent import LARGE_MODEL, SYSTEM_PROMPT, Escalator, bedrock_call  # noqa: E402
from escalator.decider import Decider  # noqa: E402
from escalator.patterns import STRICT_EXPERT_AT, AdequacyGate, TierRouter  # noqa: E402

# Not from the benchmark set. The first decider request at a new input length is slow on a Mac
# (kernel compilation), so these run before timing starts and the table measures steady state.
WARMUP = [
    "hi",
    "What is the tallest mountain in Africa?",
    "Write a function that merges two sorted lists, and explain how it handles duplicates "
    "and empty inputs. Then give its time and space complexity with a short justification.",
]

JUDGE_PROMPT = (
    "You grade answers. Given a QUESTION, a REFERENCE answer from an expert model and a "
    "CANDIDATE answer, reply with exactly one word: PASS if the candidate is correct and "
    "would satisfy the user as well as the reference, otherwise FAIL."
)


def pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def judge(question: str, reference: str, candidate: str) -> bool:
    reply = bedrock_call(
        LARGE_MODEL, JUDGE_PROMPT,
        f"QUESTION:\n{question}\n\nREFERENCE:\n{reference}\n\nCANDIDATE:\n{candidate}",
    )
    return reply.text.strip().upper().startswith("PASS")


def summarise(rows: list[dict]) -> str:
    base_cost = sum(r["baseline_cost"] for r in rows)
    esc_cost = sum(r["escalator_cost"] for r in rows)
    base_lat = [r["baseline_ms"] for r in rows]
    esc_lat = [r["escalator_ms"] for r in rows]
    decider_ms = [r["decider_ms"] for r in rows]
    paths = Counter(r["path"] for r in rows)
    by_kind: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        by_kind[r["kind"]][r["path"]] += 1

    out = [
        "# Escalator benchmark", "",
        f"{len(rows)} questions. Baseline = every question answered by `{LARGE_MODEL}`.", "",
        "| | Always-large baseline | Escalator | Change |",
        "| --- | ---: | ---: | ---: |",
        f"| Total LLM cost | ${base_cost:.6f} | ${esc_cost:.6f} | "
        f"{(esc_cost - base_cost) / base_cost:+.0%} |",
        f"| Median latency | {statistics.median(base_lat):.0f} ms | {statistics.median(esc_lat):.0f} ms | "
        f"{(statistics.median(esc_lat) - statistics.median(base_lat)) / statistics.median(base_lat):+.0%} |",
        f"| p95 latency | {pct(base_lat, .95):.0f} ms | {pct(esc_lat, .95):.0f} ms | |",
        "", f"Decider overhead per question: median {statistics.median(decider_ms):.0f} ms, "
        f"max {max(decider_ms):.0f} ms, $0 (runs locally).", "",
        "## Where each question went", "",
        "| kind | " + " | ".join(sorted(paths)) + " |",
        "| --- |" + " ---: |" * len(paths),
    ]
    for kind, counts in by_kind.items():
        out.append(f"| {kind} | " + " | ".join(str(counts[p]) for p in sorted(paths)) + " |")

    judged = [r for r in rows if r.get("judge_pass") is not None]
    if judged:
        passed = sum(r["judge_pass"] for r in judged)
        out += ["", "## Quality of answers the small model shipped", "",
                f"{passed}/{len(judged)} small-model answers judged as good as the large model's "
                f"(judge: `{LARGE_MODEL}`). Escalated and direct-large answers come from the "
                "baseline model itself; clarifying questions are not graded."]
        fails = [r for r in judged if not r["judge_pass"]]
        if fails:
            out += ["", "Judged worse:"] + [f"- `{r['id']}`: {r['prompt']}" for r in fails]
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", default=ROOT / "bench" / "questions.jsonl", type=Path)
    parser.add_argument("--judge", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--large-at", type=float, default=TierRouter.large_at,
                        help="router P(large) threshold (default %(default)s)")
    parser.add_argument("--strict", action="store_true",
                        help="strict mode (v3): code, calculations and advice go to the large model")
    args = parser.parse_args()

    questions = [json.loads(line) for line in args.questions.read_text().splitlines() if line.strip()]
    questions = questions[: args.limit] if args.limit else questions

    decider = Decider()
    health = decider.health()
    print(f"decider: {health.get('checkpoint', '?')} on {health.get('device', '?')}")
    expert_at = STRICT_EXPERT_AT if args.strict else None
    escalator = Escalator(TierRouter(decider, large_at=args.large_at, expert_at=expert_at),
                          AdequacyGate(decider))
    print(f"router: P(large) >= {args.large_at} goes straight to the large model"
          + ("" if expert_at is None else f"; so does P(code/calculation/advice) >= {expert_at}"))

    print("warming up the decider...", end=" ", flush=True)
    for prompt in WARMUP:
        escalator.router.route(prompt)
        escalator.gate.check(prompt, "Here is a short draft answer to the request above.")
    print(f"done ({decider.last_latency_ms:.0f} ms for the last call)\n")
    out_dir = ROOT / "bench" / "results" / time.strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True)

    rows = []
    for q in questions:
        baseline = bedrock_call(LARGE_MODEL, SYSTEM_PROMPT, q["prompt"])
        outcome = escalator(q["prompt"])
        row = {
            **q,
            "path": outcome.path,
            "route": outcome.route.signals,
            "gate": outcome.gate.signals if outcome.gate else None,
            "gate_reason": outcome.gate.reason if outcome.gate else None,
            "baseline_cost": baseline.cost_usd,
            "escalator_cost": outcome.cost_usd,
            "baseline_ms": baseline.latency_ms,
            "escalator_ms": outcome.latency_ms,
            "decider_ms": outcome.decider_ms,
            "baseline_answer": baseline.text,
            "escalator_answer": outcome.answer,
            "judge_pass": None,
        }
        if args.judge and outcome.path == "direct-small":
            row["judge_pass"] = judge(q["prompt"], baseline.text, outcome.answer)
        rows.append(row)
        print(f"{q['id']:<16} {outcome.path:<13} ${row['escalator_cost']:.6f} vs ${row['baseline_cost']:.6f}"
              + ("" if row["judge_pass"] is None else f"  judge={'PASS' if row['judge_pass'] else 'FAIL'}"))

    with open(out_dir / "results.jsonl", "w") as f:
        f.writelines(json.dumps(r) + "\n" for r in rows)
    summary = summarise(rows)
    (out_dir / "summary.md").write_text(summary)
    print("\n" + summary + f"\nwritten to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
