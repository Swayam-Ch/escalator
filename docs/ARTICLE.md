# Escalator: let a 2B decision model decide when your agent needs a frontier LLM

*Draft for the AWS Builder Center. Fill in the remaining [brackets] before publishing.*

## The problem

My assistant answered "what's the capital of Australia?" with the same model I'd use to design
a database schema. Most real traffic is easy, so I was paying frontier-model prices (and
waiting frontier-model latencies) for answers a model about 30× cheaper gets right.

The usual fix is a cascade: try a cheap model, escalate if it isn't good enough. The hard part
is deciding *good enough*. Asking an LLM to grade itself costs another LLM call, adds seconds
of latency, and gives you prose confidence you can't calibrate.

## The idea

[Strands Decider 2B](https://github.com/strands-labs/strands-decider) is a decision model: it
can't generate text, it can only pick options, answer yes/no, or score against a rubric. It
gives back calibrated probabilities in a single forward pass, with no API bill and no generation.
That's exactly the shape of the "is this good enough?" question.

Escalator asks it two things on every turn:

1. **Route** (`choice`): `small`, `large` or `clarify`? A confident (≥ 0.9) `clarify` asks the
   user first. P(`large`) ≥ 0.82 skips the cheap draft. Everything else goes to the small model.
2. **Gate** (3 × `noul` + 1 × `score`): does the small model's draft fully answer the request?
   Is it hedging? Is the request high-stakes? How good is it, from 0 to 3? If any check fails,
   escalate.

The model classifies, and ordinary Python decides. The whole gate policy is a few `if`s over
numbers the decider returns in one request:

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
agent's metrics, so every cost in this article is measured, not estimated:

```python
model = BedrockModel(model_id=model_id, region_name="us-east-1")
agent = Agent(model=model, system_prompt=system_prompt, callback_handler=None)
result = agent(prompt)
usage = result.metrics.accumulated_usage   # inputTokens / outputTokens -> USD via pricing.py
```

The decider runs locally with `strands-decider serve`, so its decisions cost nothing per call.

## Results

36 tuning questions plus 24 held-out questions, each set covering easy, hard, ambiguous and
high-stakes requests. Nova Micro is the small model; Claude Haiku 4.5 is the large model and the
judge.

| | v1: confident pick | v2: P(large) ≥ 0.82 | v2, held-out set |
| --- | ---: | ---: | ---: |
| LLM cost vs. always-Haiku | −68% | −20% | **−32%** |
| Small-model answers judged as good | 18 / 22 | 15 / 15 | 9 / 12 |
| Answers worse than the baseline | 4 of 33 | 0 of 33 | 3 of 23 |
| Cost on easy questions | −99% | −99% | −99% |

- **Easy questions are where the money is saved:** in v2, 12 of the 14 went to Nova Micro and
  all 12 passed the judge, at 99% lower cost on those ($0.000037 against $0.0035).
- **Hard questions mostly go straight to Haiku in v2,** so they cost the same as the baseline
  but never pay for a wasted draft.
- **Vague questions:** 3 of 4 got a clarifying question instead of a guess (1 of 3 on the
  held-out set).
- **Latency is the price on a laptop.** The decider added a median of 3.8 s per question on my
  MacBook (two decisions). The published figure is about 115 ms per decision on an RTX 3090.

![Savings vs. answer quality at each router threshold](tradeoff.png)

The overall saving depends on the traffic mix. This set is half hard or high-stakes on
purpose, so a real assistant, where most questions are easy, would save more.

## The reusable pattern: confidence-gated cascade

`escalator/patterns.py` uses only the standard library. Copy it into any agent, point it at
`strands-decider serve`, and swap in your own models. Tuning tips:

- Start strict (escalate a lot), run the benchmark with `--judge`, then loosen one knob at a time.
- Write the `true`/`false` criteria descriptions carefully. They do most of the work.
- Ask all of your gate questions in one request. The decider encodes the state once, so extra
  questions are nearly free.

## What I learned

**My first policy was wrong, and the data showed why.** v1 saved 68% but shipped four bad
answers: a DynamoDB schema, a SQL query, a JavaScript refactor and a compound-interest
calculation. I expected to fix that by tightening the gate. The numbers said otherwise: good
and bad drafts scored the same ("fully answers" 0.90–0.95, quality around 2.2 of 3). A 2B
classifier can tell whether a draft *addresses* the question, but it can't check whether code
runs or the maths adds up.

**The router had the answer all along.** Its P(large) put every easy question at 0.17–0.47 and
every hard one at 0.76–0.90. My policy waited for a confident pick (≥ 0.9) that never came, so
it threw that signal away. Branching on the probability itself, rather than on the pick, fixed
it.

**Replay before you re-run.** `bench/sweep.py` replays a saved run at every threshold in
milliseconds and with no API calls. It showed the trade-off curve (0.90: 68% saved and 4 worse;
0.81: 30% saved and 0 worse) before I spent anything on v2.

**Hold some questions back.** v2 scored 0 bad answers on the questions I tuned it on. On 24 new
questions it saved 32%, close to the sweep's prediction, but 3 of 23 answers were worse:
- a Python function, routed just under the threshold;
- a US tax question, which the gate didn't flag as high-stakes;
- a one-line rewrite. Checked by hand, this one was a strict grade, not a bad answer: Nova wrote
  "We can't proceed with the request now." So 2 of the 3 are real failures.

The perfect score was partly overfitting, and I'd rather publish the held-out number. The
fixes I'd try next are a rule sending code and tax/legal/medical questions to the large model,
and a larger Gemma 4 decider. Haiku also grades its own reference answers, which is a further
caveat on every quality number here.

Code: https://github.com/Swayam-Ch/escalator · Video: [link] · `#strands-decider-2b`
