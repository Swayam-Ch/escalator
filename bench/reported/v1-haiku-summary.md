# Escalator benchmark

36 questions. Baseline = every question answered by `us.anthropic.claude-haiku-4-5-20251001-v1:0`.

| | Always-large baseline | Escalator | Change |
| --- | ---: | ---: | ---: |
| Total LLM cost | $0.048079 | $0.015405 | -68% |
| Median latency | 2187 ms | 7589 ms | +247% |
| p95 latency | 5160 ms | 16099 ms | |

Decider overhead per question: median 5139 ms, max 26655 ms, $0 (runs locally).

## Where each question went

| kind | clarify | direct-large | direct-small | escalated |
| --- | ---: | ---: | ---: | ---: |
| easy | 0 | 0 | 12 | 2 |
| hard | 0 | 1 | 9 | 4 |
| ambiguous | 3 | 0 | 0 | 1 |
| high_stakes | 0 | 1 | 1 | 2 |

## Quality of answers the small model shipped

18/22 small-model answers judged as good as the large model's (judge: `us.anthropic.claude-haiku-4-5-20251001-v1:0`). Escalated and direct-large answers come from the baseline model itself; clarifying questions are not graded.

Judged worse:
- `hard-06`: Design a DynamoDB single-table schema for a multi-tenant SaaS app with users, projects and tasks, including the access patterns and key design.
- `hard-07`: If I invest $500 per month at 7% annual return compounded monthly, how much will I have after 20 years? Show the formula.
- `hard-08`: Write a SQL query that finds, for each department, the employee with the second-highest salary, handling ties.
- `hard-12`: Refactor this JavaScript to use async/await and handle errors: fetch(url).then(r => r.json()).then(d => console.log(d))
