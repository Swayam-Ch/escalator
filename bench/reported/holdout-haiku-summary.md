# Escalator benchmark

24 questions. Baseline = every question answered by `us.anthropic.claude-haiku-4-5-20251001-v1:0`.

| | Always-large baseline | Escalator | Change |
| --- | ---: | ---: | ---: |
| Total LLM cost | $0.034095 | $0.023217 | -32% |
| Median latency | 1742 ms | 5524 ms | +217% |
| p95 latency | 8240 ms | 13078 ms | |

Decider overhead per question: median 4153 ms, max 9402 ms, $0 (runs locally).

## Where each question went

| kind | clarify | direct-large | direct-small | escalated |
| --- | ---: | ---: | ---: | ---: |
| easy | 0 | 0 | 9 | 1 |
| hard | 0 | 6 | 2 | 0 |
| ambiguous | 1 | 0 | 0 | 2 |
| high_stakes | 0 | 2 | 1 | 0 |

## Quality of answers the small model shipped

9/12 small-model answers judged as good as the large model's (judge: `us.anthropic.claude-haiku-4-5-20251001-v1:0`). Escalated and direct-large answers come from the baseline model itself; clarifying questions are not graded.

Judged worse:
- `holdout-easy-08`: Make this sentence shorter: 'At this point in time we are not able to proceed with the request.'
- `holdout-hard-01`: Write a Python function that checks whether a string of brackets like '([]{})' is balanced, and explain its time complexity.
- `holdout-high_stakes-03`: Can I deduct my home office on my taxes if I'm a full-time employee working remotely in the US?
