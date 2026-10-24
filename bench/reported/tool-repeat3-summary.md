# run_python tool: before and after

18 calculation questions with exact answers, each asked 3 times; Correct is the mean (range) over the runs.

| Model | Tool | Correct | LLM cost per run | Median latency | Used the tool | Code runs | No answer line |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| nova-micro-v1 | off | 2.0/18 (1-3) | $0.000071 | 775 ms |  | 0 | 0 |
| nova-micro-v1 | on | 14.0/18 (13-15) | $0.001615 | 2287 ms | 54/54 | 71 | 0 |
| claude-haiku-4-5-20251001-v1 | off | 11.0/18 (10-13) | $0.046172 | 2518 ms |  | 0 | 0 |
| claude-haiku-4-5-20251001-v1 | on | 18.0/18 (18-18) | $0.052843 | 3034 ms | 54/54 | 54 | 0 |
| escalator | off | 11.7/18 (11-12) | $0.043905 | 10626 ms |  | 0 | 0 |
| escalator | on | 18.0/18 (18-18) | $0.076495 | 10065 ms | 54/54 | 195 | 0 |

Escalator routes: tool off: direct-large 36, escalated 18; tool on: direct-large 36, direct-small 1, escalated 17

## Per question

| Question | Answer | nova-micro-v1 | nova-micro-v1 +tool | claude-haiku-4-5-20251001-v1 | claude-haiku-4-5-20251001-v1 +tool | escalator | escalator +tool |
| --- | ---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `calc-01` finance | 260463.33 | ✗ 0/3 | ✗ 0/3 | ✗ 0/3 | ✓ 3/3 | ✗ 0/3 | ✓ 3/3 |
| `calc-02` finance | 386.66 | ✗ 0/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-03` finance | 13678.52 | ✗ 0/3 | ✗ 1/3 | ✗ 0/3 | ✓ 3/3 | ✗ 0/3 | ✓ 3/3 |
| `calc-04` arithmetic | 361105294 | ✗ 0/3 | ✓ 3/3 | ✗ 0/3 | ✓ 3/3 | ✗ 0/3 | ✓ 3/3 |
| `calc-05` arithmetic | 1111.111 | ✗ 0/3 | ✗ 1/3 | ✗ 1/3 | ✓ 3/3 | ✗ 1/3 | ✓ 3/3 |
| `calc-06` arithmetic | 16 | ✗ 1/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-07` arithmetic | 115 | ✗ 0/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-08` dates | 301 | ✗ 0/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 | ✗ 2/3 | ✓ 3/3 |
| `calc-09` dates | 2 | ✗ 2/3 | ✓ 3/3 | ✗ 0/3 | ✓ 3/3 | ✗ 1/3 | ✓ 3/3 |
| `calc-10` counting | 76127 | ✓ 3/3 | ✗ 2/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-11` counting | 1229 | ✗ 0/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-12` counting | 18 | ✗ 0/3 | ✓ 3/3 | ✗ 1/3 | ✓ 3/3 | ✗ 0/3 | ✓ 3/3 |
| `calc-13` counting | 242 | ✗ 0/3 | ✗ 2/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-14` counting | 1548008755920 | ✗ 0/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-15` code | 112761 | ✗ 0/3 | ✓ 3/3 | ✗ 0/3 | ✓ 3/3 | ✗ 1/3 | ✓ 3/3 |
| `calc-16` code | 111 | ✗ 0/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-17` probability | 14.7 | ✗ 0/3 | ✗ 0/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-18` statistics | 7.12 | ✗ 0/3 | ✓ 3/3 | ✗ 1/3 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 |
