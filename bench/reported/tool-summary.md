# run_python tool: before and after

18 calculation questions with exact answers.

| Model | Tool | Correct | LLM cost | Median latency | Code runs | No answer line |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| nova-micro-v1 | off | 2/18 | $0.000070 | 766 ms | 0 | 0 |
| nova-micro-v1 | on | 13/18 | $0.001452 | 2093 ms | 21 | 0 |
| claude-haiku-4-5-20251001-v1 | off | 11/18 | $0.041522 | 2364 ms | 0 | 0 |
| claude-haiku-4-5-20251001-v1 | on | 18/18 | $0.055232 | 3164 ms | 19 | 0 |

## Per question

| Question | Answer | nova-micro-v1 | nova-micro-v1 +tool | claude-haiku-4-5-20251001-v1 | claude-haiku-4-5-20251001-v1 +tool |
| --- | ---: | :---: | :---: | :---: | :---: |
| `calc-01` finance | 260463.33 | ✗ 227931.0 | ✗ 260463.2 | ✗ 177033.25 | ✓ |
| `calc-02` finance | 386.66 | ✗ 377.0 | ✓ | ✓ | ✓ |
| `calc-03` finance | 13678.52 | ✗ 15161.0 | ✗ 1367852.0 | ✗ 13493.53 | ✓ |
| `calc-04` arithmetic | 361105294 | ✗ 358619774.0 | ✓ | ✗ 361012894.0 | ✓ |
| `calc-05` arithmetic | 1111.111 | ✗ 1110.659 | ✗ 1111.0 | ✗ 1111.118 | ✓ |
| `calc-06` arithmetic | 16 | ✗ 1.0 | ✓ | ✓ | ✓ |
| `calc-07` arithmetic | 115 | ✗ 10.0 | ✓ | ✓ | ✓ |
| `calc-08` dates | 301 | ✗ 273.0 | ✓ | ✓ | ✓ |
| `calc-09` dates | 2 | ✓ | ✓ | ✗ 3.0 | ✓ |
| `calc-10` counting | 76127 | ✓ | ✓ | ✓ | ✓ |
| `calc-11` counting | 1229 | ✗ 784.0 | ✓ | ✓ | ✓ |
| `calc-12` counting | 18 | ✗ 7.0 | ✓ | ✗ 16.0 | ✓ |
| `calc-13` counting | 242 | ✗ 292.0 | ✗ 30.0 | ✓ | ✓ |
| `calc-14` counting | 1548008755920 | ✗ 15480087559209.0 | ✓ | ✓ | ✓ |
| `calc-15` code | 112761 | ✗ 245145.0 | ✓ | ✗ 111069.0 | ✓ |
| `calc-16` code | 111 | ✗ 8.0 | ✓ | ✓ | ✓ |
| `calc-17` probability | 14.7 | ✗ 14.7071 | ✗ 14.7684 | ✓ | ✓ |
| `calc-18` statistics | 7.12 | ✗ 7.6522 | ✓ | ✓ | ✓ |
