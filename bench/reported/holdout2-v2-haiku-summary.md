# Escalator benchmark

24 questions. Baseline = every question answered by `us.anthropic.claude-haiku-4-5-20251001-v1:0`.

| | Always-large baseline | Escalator | Change |
| --- | ---: | ---: | ---: |
| Total LLM cost | $0.024353 | $0.015581 | -36% |
| Median latency | 1906 ms | 13198 ms | +593% |
| p95 latency | 4999 ms | 42895 ms | |

Decider overhead per question: median 10679 ms, max 44745 ms, $0 (runs locally).

## Where each question went

| kind | clarify | direct-large | direct-small | escalated |
| --- | ---: | ---: | ---: | ---: |
| easy | 0 | 0 | 10 | 0 |
| hard | 0 | 5 | 2 | 1 |
| ambiguous | 1 | 0 | 0 | 2 |
| high_stakes | 0 | 2 | 0 | 1 |

## Quality of answers the small model shipped

12/12 small-model answers judged as good as the large model's (judge: `us.anthropic.claude-haiku-4-5-20251001-v1:0`). Escalated and direct-large answers come from the baseline model itself; clarifying questions are not graded.
