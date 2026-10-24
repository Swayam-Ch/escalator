# run_python tool: before and after

18 calculation questions with exact answers, each asked 3 times; Correct is the mean (range) over the runs.

| Model | Tool | Correct | LLM cost per run | Median latency | Used the tool | Code runs | No answer line |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| claude-haiku-4-5-20251001-v1 | off | 12.0/18 (11-13) | $0.044467 | 2550 ms |  | 0 | 0 |
| claude-haiku-4-5-20251001-v1 | on | 18.0/18 (18-18) | $0.056033 | 2983 ms | 54/54 | 57 | 0 |
| escalator-verify | on | 17.7/18 (17-18) | $0.027133 | 10683 ms | 53/54 | 172 | 1 |

escalator-verify routes: tool on: error 1, escalated 21, verified 32

## Per question

| Question | Answer | claude-haiku-4-5-20251001-v1 | claude-haiku-4-5-20251001-v1 +tool | escalator-verify +tool |
| --- | ---: | :---: | :---: | :---: |
| `calc-01` finance | 260463.33 | ✗ 0/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-02` finance | 386.66 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-03` finance | 13678.52 | ✗ 0/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-04` arithmetic | 361105294 | ✗ 0/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-05` arithmetic | 1111.111 | ✗ 2/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-06` arithmetic | 16 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-07` arithmetic | 115 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-08` dates | 301 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-09` dates | 2 | ✗ 2/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-10` counting | 76127 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-11` counting | 1229 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-12` counting | 18 | ✗ 0/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-13` counting | 242 | ✓ 3/3 | ✓ 3/3 | ✗ 2/3 |
| `calc-14` counting | 1548008755920 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-15` code | 112761 | ✗ 0/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-16` code | 111 | ✗ 2/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-17` probability | 14.7 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 |
| `calc-18` statistics | 7.12 | ✓ 3/3 | ✓ 3/3 | ✓ 3/3 |
