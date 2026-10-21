# Escalator: let a 2B decision model decide when your agent needs the bigger LLM

## The problem

My assistant answered "what's the capital of Australia?" with the same model I'd use to design
a database schema. Most real traffic is easy, so I was paying large-model prices (and
waiting large-model latencies) for answers a model about 30× cheaper gets right.

The usual fix is a cascade: try a cheap model, escalate if it isn't good enough. The hard part
is deciding *good enough*. Asking an LLM to grade itself costs another LLM call, adds seconds
of latency, and gives you prose confidence you can't calibrate.

## The idea

[Strands Decider 2B](https://github.com/strands-labs/strands-decider) is a decision model: it
can't generate text, it can only pick options, answer yes/no, or score against a rubric. It
returns calibrated probabilities from a single forward pass, which is what an "is this good
enough?" check needs.

Escalator asks it two things on every turn:

1. Route (`choice`): `small`, `large` or `clarify`? A confident (≥ 0.9) `clarify` asks the
   user first. P(`large`) ≥ 0.82 skips the cheap draft. Everything else goes to the small model.
2. Gate (3 × `noul` + 1 × `score`): does the small model's draft fully answer the request?
   Is it hedging? Is the request high-stakes? How good is it, from 0 to 3? If any check fails,
   escalate.

The decider only classifies. The gate policy itself is a few `if`s in plain Python over the
numbers it returns in one request:

```python
a = self.decider.ask(state, GATE_QUESTIONS)   # 3 yes/no questions + 1 rubric score, one round trip
if a["high_stakes"]["noul"] > p.max_high_stakes:
    return Verdict(ESCALATE, "high-stakes request", signals, latency)
if a["answers"]["noul"] < p.min_answers:
    return Verdict(ESCALATE, "draft does not fully answer", signals, latency)
if a["hedging"]["noul"] > p.max_hedging:
    return Verdict(ESCALATE, "draft is hedging", signals, latency)
if a["quality"]["score"] < p.min_quality:
    return Verdict(ESCALATE, "draft quality below bar", signals, latency)
return Verdict(ACCEPT, "draft is good enough", signals, latency)
```

Because the verdict is a number, the agent can't argue its way past it, and every decision is
logged with the exact scores that caused it.

## Building it with Strands Agents and Bedrock

Both tiers are ordinary Strands agents on Amazon Bedrock. Token usage comes straight from the
agent's metrics, so every cost in this article is based on measured token counts:

```python
model = BedrockModel(model_id=model_id, region_name="us-east-1")
agent = Agent(model=model, system_prompt=system_prompt, callback_handler=None)
result = agent(prompt)
usage = result.metrics.accumulated_usage   # inputTokens / outputTokens -> USD via pricing.py
```

The decider runs locally with `strands-decider serve`, so its decisions cost nothing per call.

## Results

I ran 36 tuning questions and 24 held-out questions, each set mixing easy, hard, ambiguous and
high-stakes requests. Nova Micro is the small model; Claude Haiku 4.5 is the large model and the
judge.

| | v1: confident pick | v2: P(large) ≥ 0.82 | v2, held-out set |
| --- | ---: | ---: | ---: |
| LLM cost vs. always-Haiku | −68% | −20% | **−32%** |
| Small-model answers judged as good | 18 / 22 | 15 / 15 | 9 / 12 |
| Answers worse than the baseline | 4 of 33 | 0 of 33 | 3 of 23 |
| Cost on easy questions | −99% | −99% | −99% |

- Most of the saving comes from easy questions. In v2, 12 of the 14 went to Nova Micro and all
  12 passed the judge, at 99% lower cost ($0.000037 against $0.0035).
- In v2, hard questions mostly go straight to Haiku, so they cost the same as the baseline
  but never pay for a wasted draft.
- 3 of the 4 vague questions got a clarifying question back instead of a guess (1 of 3 on the
  held-out set).
- On a laptop, the price is latency. The decider added a median of 3.8 s per question (two
  decisions) on my MacBook. The published figure is about 115 ms per decision on an RTX 3090.

![Savings vs. answer quality at each router threshold](tradeoff.png)

The overall saving depends on the traffic mix. This set is half hard or high-stakes on
purpose, so a real assistant, where most questions are easy, would save more.

## The reusable pattern: confidence-gated cascade

`escalator/patterns.py` uses only the standard library. Copy it into any agent, point it at
`strands-decider serve`, and swap in your own models. `examples/minimal_cascade.py` shows the
whole pattern with plain Python functions in place of the LLMs: no Strands, no Bedrock, no AWS
account. Tuning tips:

- Start strict (escalate a lot), run the benchmark with `--judge`, then loosen one knob at a time.
- Write the `true`/`false` criteria descriptions carefully. They do most of the work.
- Ask all of your gate questions in one request. The decider encodes the state once, so extra
  questions are nearly free.

## What I learned

My first policy saved 68% but shipped four bad answers: a DynamoDB schema, a SQL query, a
JavaScript refactor and a compound-interest calculation. I expected to fix that by tightening
the gate, but good and bad drafts got the same scores ("fully answers" 0.90 to 0.95, quality
around 2.2 of 3). A 2B classifier can tell whether a draft *addresses* the question. It can't
check whether code runs or the maths adds up.

The router's probabilities already separated easy from hard. P(large) was 0.17 to 0.47 for
every easy question and 0.76 to 0.90 for every hard one, but my policy waited for a confident
pick (≥ 0.9) that never came, so it threw that signal away. v2 branches on the probability
itself instead of the pick, and that fixed it.

Before spending anything on v2, I replayed the saved run with `bench/sweep.py`, which tries
every threshold in milliseconds without any API calls. That gave me the trade-off curve: 68%
saved and 4 worse answers at 0.90, 30% saved and 0 worse at 0.81.

I also held some questions back. v2 scored 0 bad answers on the questions I tuned it on. On 24
new questions it saved 32%, close to what the sweep predicted, but 3 of 23 answers were worse:
- a Python function, routed just under the threshold;
- a US tax question, which the gate didn't flag as high-stakes;
- a one-line rewrite. I checked this one by hand, and it was a strict grade rather than a bad
  answer: Nova wrote "We can't proceed with the request now." So 2 of the 3 are real failures.

The perfect score was partly overfitting, and I'd rather publish the held-out number.

So I tried the obvious fix. v3 adds one yes/no question to the router's call: does the request
ask for code, a multi-step calculation, or advice on tax, law, medicine or money? If so, Haiku
answers directly. That rule came from looking at the first held-out set, so I tested v2 and v3
on a second set of 24 questions neither had seen. v2 saved 36% with 0 worse answers; v3 saved
11%, also with 0 worse answers. v2 had nothing for v3 to catch, and v3 sent working code
answers and "What is 15% of 200?" to Haiku. I kept v2 as the default and left v3 in as an
opt-in strict mode for products where one wrong answer about code or money is expensive.
Across both held-out sets, v2 saved 34% with 2 real failures in 46 answers.

Next I'd try a larger Gemma 4 decider. Two more caveats: Haiku grades its own reference
answers, and Haiku 4.5 is a generation behind today's Claude models. Both models are set by
environment variables, but I haven't measured the current generation yet.

Code: https://github.com/Swayam-Ch/escalator · Video: https://youtu.be/PtXiIiXiwM4 · `#strands-decider-2b`
