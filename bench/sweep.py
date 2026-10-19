"""Replay a benchmark run at different router thresholds, with no new LLM or decider calls.

    python bench/sweep.py bench/reported/v1-haiku-results.jsonl

For each P(large) threshold it re-decides every question from the router scores that run
recorded. A question that newly goes to the large model is costed at its baseline answer
(same model, same prompt) and counts as matching it. A question the run sent straight to
the large model is kept as it was, since there is no small draft to replay.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def replay(rows: list[dict], large_at: float, expert_at: float | None = None) -> dict:
    cost, shipped_small, worse = 0.0, 0, []
    for r in rows:
        expert = expert_at is not None and r["route"].get("p_expert", 0) >= expert_at
        moves_large = r["path"] in {"direct-small", "escalated"} and (
            r["route"].get("p_large", 0) >= large_at or expert)
        if moves_large:
            cost += r["baseline_cost"]
            continue
        cost += r["escalator_cost"]
        if r["path"] == "direct-small":
            shipped_small += 1
            if r.get("judge_pass") is False:
                worse.append(r["id"])
    baseline = sum(r["baseline_cost"] for r in rows)
    return {"large_at": large_at, "cost": cost, "saving": 1 - cost / baseline,
            "shipped_small": shipped_small, "worse": worse}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.results.read_text().splitlines() if line.strip()]

    print("| P(large) threshold | Escalator cost | Saving vs baseline | Small answers shipped | Judged worse |")
    print("| ---: | ---: | ---: | ---: | --- |")
    previous = None
    for step in range(50, 100):
        result = replay(rows, step / 100)
        key = (result["shipped_small"], tuple(result["worse"]))
        if key == previous:
            continue
        previous = key
        worse = ", ".join(result["worse"]) or "none"
        print(f"| {result['large_at']:.2f} | ${result['cost']:.6f} | {result['saving']:.0%} | "
              f"{result['shipped_small']} | {len(result['worse'])}: {worse} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
