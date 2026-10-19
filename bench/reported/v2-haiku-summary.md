# Escalator benchmark

36 questions. Baseline = every question answered by `us.anthropic.claude-haiku-4-5-20251001-v1:0`.

| | Always-large baseline | Escalator | Change |
| --- | ---: | ---: | ---: |
| Total LLM cost | $0.051259 | $0.041147 | -20% |
| Median latency | 2299 ms | 6203 ms | +170% |
| p95 latency | 6515 ms | 12811 ms | |

Decider overhead per question: median 3835 ms, max 27990 ms, $0 (runs locally).

## Where each question went

| kind | clarify | direct-large | direct-small | escalated |
| --- | ---: | ---: | ---: | ---: |
| easy | 0 | 0 | 12 | 2 |
| hard | 0 | 10 | 3 | 1 |
| ambiguous | 3 | 0 | 0 | 1 |
| high_stakes | 0 | 2 | 0 | 2 |

## Quality of answers the small model shipped

15/15 small-model answers judged as good as the large model's (judge: `us.anthropic.claude-haiku-4-5-20251001-v1:0`). Escalated and direct-large answers come from the baseline model itself; clarifying questions are not graded.
