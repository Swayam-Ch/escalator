# Escalator benchmark

24 questions. Baseline = every question answered by `us.anthropic.claude-haiku-4-5-20251001-v1:0`.

| | Always-large baseline | Escalator | Change |
| --- | ---: | ---: | ---: |
| Total LLM cost | $0.022278 | $0.019805 | -11% |
| Median latency | 1909 ms | 6863 ms | +259% |
| p95 latency | 5199 ms | 52572 ms | |

Decider overhead per question: median 3918 ms, max 98477 ms, $0 (runs locally).

## Where each question went

| kind | clarify | direct-large | direct-small | escalated |
| --- | ---: | ---: | ---: | ---: |
| easy | 0 | 1 | 9 | 0 |
| hard | 0 | 8 | 0 | 0 |
| ambiguous | 1 | 0 | 0 | 2 |
| high_stakes | 0 | 3 | 0 | 0 |

## Quality of answers the small model shipped

9/9 small-model answers judged as good as the large model's (judge: `us.anthropic.claude-haiku-4-5-20251001-v1:0`). Escalated and direct-large answers come from the baseline model itself; clarifying questions are not graded.
