"""Before and after the run_python tool: the same questions, each model with the tool off and on.

    python bench/run_tool_bench.py              # bench/calc_questions.jsonl, small and large models
    python bench/run_tool_bench.py --limit 3    # quick check

Every question has an exact answer, so correctness is checked by code, not by an LLM judge.
Writes bench/results/tools-<timestamp>/results.jsonl and summary.md.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from escalator.agent import LARGE_MODEL, SMALL_MODEL, SYSTEM_PROMPT, bedrock_call  # noqa: E402
from escalator.tools import make_run_python  # noqa: E402

ANSWER_FORMAT = (
    "End your reply with a final line in the form ANSWER: <number>, with no units, currency "
    "signs or thousands separators."
)
ANSWER_LINE = re.compile(r"ANSWER:\s*\**\s*\$?\s*(-?[\d,]*\.?\d+(?:[eE][-+]?\d+)?)")


def parse_answer(text: str) -> float | None:
    matches = ANSWER_LINE.findall(text)
    if not matches:
        return None
    try:
        return float(matches[-1].replace(",", ""))
    except ValueError:
        return None


def is_correct(predicted: float | None, answer: float, tol: float) -> bool:
    return predicted is not None and abs(predicted - answer) <= tol + 1e-9


def short(model_id: str) -> str:
    return model_id.split(".")[-1].split(":")[0]


def summarise(rows: list[dict], configs: list[tuple[str, bool]]) -> str:
    out = ["# run_python tool: before and after", "",
           f"{len({r['id'] for r in rows})} calculation questions with exact answers.", "",
           "| Model | Tool | Correct | LLM cost | Median latency | Code runs | No answer line |",
           "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for model, tool in configs:
        mine = [r for r in rows if r["model"] == model and r["tool"] == tool]
        if not mine:
            continue
        correct = sum(r["correct"] for r in mine)
        out.append(
            f"| {short(model)} | {'on' if tool else 'off'} | {correct}/{len(mine)} | "
            f"${sum(r['cost'] for r in mine):.6f} | {statistics.median(r['latency_ms'] for r in mine):.0f} ms | "
            f"{sum(r['tool_calls'] for r in mine)} | {sum(r['predicted'] is None for r in mine)} |")
    ids = list(dict.fromkeys(r["id"] for r in rows))
    labels = [f"{short(m)} {'+tool' if t else ''}".strip() for m, t in configs]
    out += ["", "## Per question", "", "| Question | Answer | " + " | ".join(labels) + " |",
            "| --- | ---: |" + " :---: |" * len(configs)]
    for qid in ids:
        first = next(r for r in rows if r["id"] == qid)
        cells = []
        for model, tool in configs:
            r = next((r for r in rows if r["id"] == qid and r["model"] == model and r["tool"] == tool), None)
            cells.append("" if r is None else ("✓" if r["correct"] else f"✗ {r['predicted']}"))
        out.append(f"| `{qid}` {first['kind']} | {first['answer']} | " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", default=ROOT / "bench" / "calc_questions.jsonl", type=Path)
    parser.add_argument("--models", default="small,large", help="small, large, or both")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    questions = [json.loads(line) for line in args.questions.read_text().splitlines() if line.strip()]
    questions = questions[: args.limit] if args.limit else questions
    models = [{"small": SMALL_MODEL, "large": LARGE_MODEL}[m] for m in args.models.split(",")]
    configs = [(model, tool) for model in models for tool in (False, True)]
    runs: list[dict] = []
    run_python = make_run_python(log=runs)

    out_dir = ROOT / "bench" / "results" / time.strftime("tools-%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True)
    rows = []
    for q in questions:
        for model, tool in configs:
            row = {**q, "model": model, "tool": tool}
            runs.clear()
            try:
                reply = bedrock_call(model, f"{SYSTEM_PROMPT}\n\n{ANSWER_FORMAT}", q["prompt"],
                                     [run_python] if tool else None)
                predicted = parse_answer(reply.text)
                row.update(text=reply.text, predicted=predicted, cost=reply.cost_usd,
                           latency_ms=reply.latency_ms, tool_calls=reply.tool_calls,
                           correct=is_correct(predicted, q["answer"], q["tol"]), error=None)
            except Exception as exc:  # one failed call should not lose the whole run
                row.update(text="", predicted=None, cost=0.0, latency_ms=0.0, tool_calls=0,
                           correct=False, error=f"{type(exc).__name__}: {exc}")
            row["runs"] = list(runs)  # the code the model ran and what it printed
            rows.append(row)
            mark = "✓" if row["correct"] else "✗"
            print(f"{q['id']:<8} {short(model):<28} tool={'on ' if tool else 'off'} {mark} "
                  f"{row['predicted']!s:<16} runs={row['tool_calls']} ${row['cost']:.6f}"
                  + (f"  {row['error']}" if row["error"] else ""))

    with open(out_dir / "results.jsonl", "w") as f:
        f.writelines(json.dumps(r) + "\n" for r in rows)
    summary = summarise(rows, configs)
    (out_dir / "summary.md").write_text(summary)
    print("\n" + summary + f"\nwritten to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
