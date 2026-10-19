# Escalator

**A Strands agent that only pays for a big Bedrock model when Strands Decider 2B says it has to.**

Most questions people ask an assistant are easy. Sending all of them to a frontier model is
like routing every support ticket to your principal engineer. Escalator puts a ~2B decision
model (Strands Decider 2B, running locally, ~100–300 ms per decision) in front of two Bedrock
models and lets it make two calibrated decisions on every turn:

```mermaid
flowchart LR
    U[User request] --> R{"Decision 1 · ROUTE<br/>(decider choice)"}
    R -- "clarify @ ≥0.9" --> C[Small model asks a<br/>clarifying question]
    R -- "P(large) ≥ 0.82" --> L[Large model answers]
    R -- "small, or unsure" --> S[Small model drafts]
    S --> G{"Decision 2 · GATE<br/>(3 nouls + 1 score)"}
    G -- accept --> A[Ship the draft]
    G -- escalate --> L
```

| Decision | Decider question type | Acts when | Otherwise |
| --- | --- | --- | --- |
| **Route**: which tier should answer? | `choice` over `small` / `large` / `clarify` | P(`large`) ≥ 0.82, or `clarify` with confidence ≥ 0.9 | cheap draft, then gate |
| **Gate**: is the small model's draft good enough? | `noul` × 3 (answers fully? hedging? high stakes?) + `score` (4-level rubric) | every check passes | escalate to the large model |

The model **classifies**, the code **decides**: each verdict is a number your `if` statements
branch on, so the policy is auditable and tunable, and the agent can't argue its way past it.
The default is safe: when the router is unsure, the cheap draft still has to pass the gate.

## The reusable decision pattern: *confidence-gated cascade*

[`escalator/patterns.py`](escalator/patterns.py) is self-contained (standard library only, no
Strands or Bedrock imports). Use it in any agent:

```python
from escalator.decider import Decider
from escalator.patterns import TierRouter, AdequacyGate, GatePolicy

decider = Decider()                                  # http://127.0.0.1:8099
route = TierRouter(decider, large_at=0.82).route(prompt)  # Verdict(action="small"|"large"|"clarify", ...)
if route.action == "small":
    draft = my_cheap_llm(prompt)
    verdict = AdequacyGate(decider, GatePolicy(min_quality=2.0)).check(prompt, draft)
    answer = draft if verdict.action == "accept" else my_expensive_llm(prompt)
```

Every `Verdict` carries `action`, a human-readable `reason`, the raw `signals` it branched on,
and the decider's `latency_ms`, which makes logging and threshold-tuning straightforward.

**Why it works with Decider 2B specifically:** the decider's confidences are calibrated (on
unseen short classification tasks, answers at ≥ 0.9 confidence are right ~95% of the time,
per the [strands-decider evaluation](https://github.com/strands-labs/strands-decider/blob/main/evaluation/results.md)).
An LLM's self-reported confidence gives you no such guarantee. Each decision is also a single
forward pass, with no generation and no API bill, so it can sit on the hot path of every request.

**Knobs** (all in code): `TierRouter.large_at` and `TierRouter.sure`, plus `GatePolicy.min_answers`, `max_hedging`,
`max_high_stakes` and `min_quality`. Raise them to escalate more often (higher quality);
lower them to save more. `python bench/sweep.py <results.jsonl>` replays a saved benchmark
run at every router threshold, without new LLM calls, so you can choose `large_at` from data.

## Quick start

Requirements: Python 3.10+, AWS credentials with Bedrock access to the two models (default
`us.amazon.nova-micro-v1:0` and `us.anthropic.claude-sonnet-4-5-20250929-v1:0`, enable them in
the Bedrock console), and a machine that can run the 2B decider (CPU works; Apple silicon or a
GPU is faster).

```bash
git clone <this repo> && cd escalator
python -m venv .venv && source .venv/bin/activate
pip install -e ".[decider,dev]"
cp .env.example .env   # then edit; export the variables or use your AWS profile

# terminal 1: the decision model (downloads ~4 GB from Hugging Face on first run)
strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8099

# terminal 2: the agent
escalator                                   # interactive
escalator "What is the capital of Australia?"
```

Example trace (illustrative numbers; yours will differ):

```
decider route  -> small  (simple request; small model drafts, gate checks)  {...} 140ms
decider gate   -> accept (draft is good enough)  {'answers': 0.97, 'hedging': 0.03, 'high_stakes': 0.02, 'quality': 2.8} 180ms
  nova-micro-v1: 21+12 tok, $0.000002, 410ms

[nova-micro-v1] Canberra.
```

## Benchmark: measure the savings

```bash
python bench/run_bench.py            # cost + latency vs. always-large baseline (36 questions)
python bench/run_bench.py --judge    # + the large model grades every answer the small model shipped
```

The set in [`bench/questions.jsonl`](bench/questions.jsonl) mixes easy, hard, ambiguous and
high-stakes requests. Results go to `bench/results/<timestamp>/summary.md`: total cost, median
and p95 latency, decider overhead, where each kind of question was routed, and (with `--judge`)
how many shipped small-model answers matched the large model's quality.

> Results: _paste your `summary.md` table here after running it._

Prices live in [`escalator/pricing.py`](escalator/pricing.py). Check them against the
[Bedrock pricing page](https://aws.amazon.com/bedrock/pricing/) before you publish numbers.

## Tests

```bash
pytest -q
```

The tests use a fake decider and fake models, so they need neither AWS nor the model.

## Project layout

```
escalator/patterns.py   the reusable decision pattern (router + gate + policy)
escalator/decider.py    tiny urllib client for `strands-decider serve`
escalator/agent.py      the cascade, built on Strands Agents + BedrockModel
escalator/pricing.py    Bedrock prices for cost accounting
escalator/cli.py        interactive demo with a decision trace
bench/                  benchmark questions and runner
docs/                   Builder Center article draft + demo video script
```

## Limitations

- Decider 2B is an experimental model, not a production product. The questions and thresholds
  here were chosen by hand; tune them on your own traffic using the benchmark.
- Single-turn questions only. Each request goes to a fresh agent.
- An escalated request pays for the small draft *and* the large answer, so savings depend on
  your mix of easy and hard traffic. The benchmark shows the break-even for your own mix.

MIT licensed. `#strands-decider-2b`
