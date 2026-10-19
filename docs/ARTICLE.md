# Escalator: let a 2B decision model decide when your agent needs a frontier LLM

*Draft for the AWS Builder Center. Replace the bracketed numbers with your benchmark results.*

## The problem

My assistant answered "what's the capital of Australia?" with the same model I'd use to design
a database schema. Most real traffic is easy, so I was paying frontier-model prices (and
waiting frontier-model latencies) for answers a model 100× cheaper gets right.

The usual fix is a cascade: try a cheap model, escalate if it isn't good enough. The hard part
is deciding *good enough*. Asking an LLM to grade itself costs another LLM call, adds seconds
of latency, and gives you prose confidence you can't calibrate.

## The idea

[Strands Decider 2B](https://github.com/strands-labs/strands-decider) is a decision model: it
can't generate text, it can only pick options, answer yes/no, or score against a rubric. It
gives back calibrated probabilities in a single forward pass of about 100–300 ms on a laptop.
That's exactly the shape of the "is this good enough?" question.

Escalator asks it two things on every turn:

1. **Route** (`choice`): `small`, `large` or `clarify`? The agent acts only on a confident
   (≥ 0.9) `large` or `clarify`. Anything else takes the cheap path, because the gate will catch it.
2. **Gate** (3 × `noul` + 1 × `score`): does the small model's draft fully answer the request?
   Is it hedging? Is the request high-stakes? How good is it, from 0 to 3? If any check fails,
   escalate.

The model classifies, and ordinary Python decides. [Show `AdequacyGate.check` here.]

## Building it with Strands Agents and Bedrock

[Show `bedrock_call`: a stateless `Agent(model=BedrockModel(...))`, with token usage read from
`result.metrics.accumulated_usage` for exact cost accounting.]

## Results

[Paste the table from `bench/results/<ts>/summary.md`.]

- Cost: [X]% lower than always using Claude Sonnet.
- Median latency: [Y]% lower. The decider adds a median of [Z] ms.
- Quality: [N/M] answers the small model shipped were judged as good as Sonnet's.
- Where things went: easy questions mostly stayed small, hard ones went large, and ambiguous
  ones got a clarifying question.

## The reusable pattern: confidence-gated cascade

`escalator/patterns.py` uses only the standard library. Copy it into any agent, point it at
`strands-decider serve`, and swap in your own models. Tuning tips:

- Start strict (escalate a lot), run the benchmark with `--judge`, then loosen one knob at a time.
- Write the `true`/`false` criteria descriptions carefully. They do most of the work.
- Ask all of your gate questions in one request. The decider encodes the state once, so extra
  questions are nearly free.

## What I learned

[A threshold that surprised you, a question wording that mattered, a failure case.]

Code: [repo link] · Video: [link] · `#strands-decider-2b`
