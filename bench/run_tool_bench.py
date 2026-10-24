"""Before and after the run_python tool: the same questions, each model with the tool off and on.

    python bench/run_tool_bench.py                        # bench/calc_questions.jsonl, small and large models
    python bench/run_tool_bench.py --limit 3              # quick check
    python bench/run_tool_bench.py --repeat 3             # ask everything 3 times, report the spread
    python bench/run_tool_bench.py --models escalator     # the whole agent: decider route, model + tool, gate
    python bench/run_tool_bench.py --models verify        # the whole agent in verify mode (tool on only)
    python bench/run_tool_bench.py --summarise bench/results/tools-<timestamp>   # rebuild summary.md

Every question has an exact answer, so correctness is checked by code, not by an LLM judge.
`--models escalator` and `verify` need the decider running (see README "Quick start").
Writes bench/results/tools-<timestamp>/results.jsonl and summary.md.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from escalator.agent import LARGE_MODEL, SMALL_MODEL, SYSTEM_PROMPT, bedrock_call  # noqa: E402
from escalator.tools import make_run_python  # noqa: E402

ESCALATOR = "escalator"   # stands in for a model id: the full cascade, with whichever models it routes to
VERIFY = "escalator-verify"   # the same, with two small drafts checked against their code
AGENTS = (ESCALATOR, VERIFY)
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


def with_answer_format(call):
    """Wrap a CallModel so answering calls ask for an ANSWER line; the clarify call is left alone."""
    def wrapped(model_id, system_prompt, prompt, tools=None):
        if system_prompt == SYSTEM_PROMPT:
            system_prompt = f"{SYSTEM_PROMPT}\n\n{ANSWER_FORMAT}"
        return call(model_id, system_prompt, prompt, tools)
    return wrapped


def correct_cell(scores: list[int], n: int) -> str:
    if len(scores) == 1:
        return f"{scores[0]}/{n}"
    return f"{statistics.mean(scores):.1f}/{n} ({min(scores)}-{max(scores)})"


def summarise(rows: list[dict], configs: list[tuple[str, bool]]) -> str:
    reps = sorted({r.get("rep", 0) for r in rows})
    n = len({r["id"] for r in rows})
    out = ["# run_python tool: before and after", "",
           f"{n} calculation questions with exact answers"
           + (f", each asked {len(reps)} times; Correct is the mean (range) over the runs." if len(reps) > 1 else "."),
           "", "| Model | Tool | Correct | LLM cost per run | Median latency | Used the tool | Code runs | No answer line |",
           "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for model, tool in configs:
        mine = [r for r in rows if r["model"] == model and r["tool"] == tool]
        if not mine:
            continue
        scores = [sum(r["correct"] for r in mine if r.get("rep", 0) == rep) for rep in reps]
        used = f"{sum(r['tool_calls'] > 0 for r in mine)}/{len(mine)}" if tool else ""
        out.append(
            f"| {short(model)} | {'on' if tool else 'off'} | {correct_cell(scores, n)} | "
            f"${sum(r['cost'] for r in mine) / len(reps):.6f} | "
            f"{statistics.median(r['latency_ms'] for r in mine):.0f} ms | {used} | "
            f"{sum(r['tool_calls'] for r in mine)} | {sum(r['predicted'] is None for r in mine)} |")
    for agent in AGENTS:
        paths = [(tool, Counter(r["path"] or "error" for r in rows if r["model"] == agent and r["tool"] == tool))
                 for tool in (False, True)]
        if any(c for _, c in paths):
            out += ["", f"{agent} routes: " + "; ".join(
                f"tool {'on' if tool else 'off'}: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items()))
                for tool, c in paths if c)]
    ids = list(dict.fromkeys(r["id"] for r in rows))
    labels = [f"{short(m)} {'+tool' if t else ''}".strip() for m, t in configs]
    out += ["", "## Per question", "", "| Question | Answer | " + " | ".join(labels) + " |",
            "| --- | ---: |" + " :---: |" * len(configs)]
    for qid in ids:
        first = next(r for r in rows if r["id"] == qid)
        cells = []
        for model, tool in configs:
            mine = [r for r in rows if r["id"] == qid and r["model"] == model and r["tool"] == tool]
            if not mine:
                cells.append("")
            elif len(mine) == 1:
                cells.append("✓" if mine[0]["correct"] else f"✗ {mine[0]['predicted']}")
            else:
                right = sum(r["correct"] for r in mine)
                cells.append(f"{'✓' if right == len(mine) else '✗'} {right}/{len(mine)}")
        out.append(f"| `{qid}` {first['kind']} | {first['answer']} | " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def build_escalator(tools: list, verify: bool = False):
    from escalator.agent import Escalator
    from escalator.decider import Decider
    from escalator.patterns import AdequacyGate, TierRouter

    decider = Decider()
    decider.health()  # fail early if the decider isn't running
    return Escalator(TierRouter(decider), AdequacyGate(decider), call=with_answer_format(bedrock_call),
                     tools=tools, verify=verify)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", default=ROOT / "bench" / "calc_questions.jsonl", type=Path)
    parser.add_argument("--models", default="small,large", help="comma list of small, large, escalator, verify")
    parser.add_argument("--repeat", type=int, default=1, help="ask every question this many times")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--summarise", type=Path, help="rebuild summary.md from a saved results folder and exit")
    args = parser.parse_args()

    if args.summarise:
        rows = [json.loads(line) for line in (args.summarise / "results.jsonl").read_text().splitlines() if line]
        summary = summarise(rows, list(dict.fromkeys((r["model"], r["tool"]) for r in rows)))
        (args.summarise / "summary.md").write_text(summary)
        print(summary)
        return 0

    questions = [json.loads(line) for line in args.questions.read_text().splitlines() if line.strip()]
    questions = questions[: args.limit] if args.limit else questions
    models = [{"small": SMALL_MODEL, "large": LARGE_MODEL, ESCALATOR: ESCALATOR, "verify": VERIFY}[m]
              for m in args.models.split(",")]
    configs = [(model, tool) for model in models for tool in (False, True) if tool or model != VERIFY]
    runs: list[dict] = []
    run_python = make_run_python(log=runs)
    escalators = {}
    if ESCALATOR in models:
        escalators.update({(ESCALATOR, tool): build_escalator([run_python] if tool else []) for tool in (False, True)})
    if VERIFY in models:
        escalators[(VERIFY, True)] = build_escalator([run_python], verify=True)

    out_dir = ROOT / "bench" / "results" / time.strftime("tools-%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True)
    rows = []
    for rep in range(args.repeat):
        for q in questions:
            for model, tool in configs:
                row = {**q, "model": model, "tool": tool, "rep": rep, "path": None, "final_model": model}
                runs.clear()
                try:
                    if model in AGENTS:
                        outcome = escalators[(model, tool)](q["prompt"])
                        text, cost, latency = outcome.answer, outcome.cost_usd, outcome.latency_ms
                        calls = sum(r.tool_calls for r in outcome.replies)
                        row.update(path=outcome.path, final_model=outcome.final_model)
                    else:
                        reply = bedrock_call(model, f"{SYSTEM_PROMPT}\n\n{ANSWER_FORMAT}", q["prompt"],
                                             [run_python] if tool else None)
                        text, cost, latency, calls = reply.text, reply.cost_usd, reply.latency_ms, reply.tool_calls
                    predicted = parse_answer(text)
                    row.update(text=text, predicted=predicted, cost=cost, latency_ms=latency, tool_calls=calls,
                               correct=is_correct(predicted, q["answer"], q["tol"]), error=None)
                except Exception as exc:  # one failed call should not lose the whole run
                    row.update(text="", predicted=None, cost=0.0, latency_ms=0.0, tool_calls=0,
                               correct=False, error=f"{type(exc).__name__}: {exc}")
                row["runs"] = list(runs)  # the code the model ran and what it printed
                rows.append(row)
                mark = "✓" if row["correct"] else "✗"
                print(f"r{rep} {q['id']:<8} {short(model):<28} tool={'on ' if tool else 'off'} {mark} "
                      f"{row['predicted']!s:<16} runs={row['tool_calls']} ${row['cost']:.6f}"
                      + (f"  {row['path']} -> {short(row['final_model'])}" if row["path"] else "")
                      + (f"  {row['error']}" if row["error"] else ""))

    with open(out_dir / "results.jsonl", "w") as f:
        f.writelines(json.dumps(r) + "\n" for r in rows)
    summary = summarise(rows, configs)
    (out_dir / "summary.md").write_text(summary)
    print("\n" + summary + f"\nwritten to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
