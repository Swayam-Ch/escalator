# Submission checklist

Requirements as found for the Agent Experience Hackathon (Strands Decider). Check the official
rules page for the final wording and the deadline (sources disagree: Oct 23 or Oct 30, 2026).

| Requirement | Where | Status |
| --- | --- | --- |
| Agent uses Strands Decider 2B for a meaningful decision | `escalator/patterns.py`: route (choice) and gate (noul ×3 + score) on every request | Done |
| Paired with Amazon Bedrock | `escalator/agent.py`: Strands `Agent` + `BedrockModel` (Nova Micro, Claude Haiku 4.5) | Done |
| Public code repository | https://github.com/Swayam-Ch/escalator | Done |
| At least one reusable decision pattern | README "The reusable decision pattern", `escalator/patterns.py`, `examples/minimal_cascade.py` | Done |
| Builder Center article | https://builder.aws.com/post/3Kv1OQQQLOMoGHuLHIIp4OkN3O1_h/escalator-let-a-2b-decision-model-decide-when-your-agent-needs-the-bigger-llm | Done |
| Demo video under 3 minutes | https://youtu.be/PtXiIiXiwM4 | Done |
| Measured latency or cost improvement (bonus) | `bench/reported/`, README Results | Done (v1, v2, held-out) |

## Before submitting

- [x] Run the held-out set and add it to the README and the article.
- [ ] Save its files to `bench/reported/holdout-haiku-*` and push them.
- [x] Record the video, upload it and link it in the README and the article.
- [x] Publish the article on Builder Center with the `#strands-decider-2b` tag.
- [ ] On GitHub, add the `strands-decider-2b` topic and a one-line description to the repo.
- [ ] Open the repo in a private window and check that the README reads well from top to bottom.
- [ ] Submit the repo, article and video links on the hackathon page.

## What the judges score (as found: creativity 30%, Decider use + pattern 30%, communication 25%)

- **Decider use:** all three question types (choice, noul, score), calibrated thresholds owned by
  code, and a data-driven policy change from v1 to v2.
- **Reusable pattern:** one stdlib-only file, tunable `GatePolicy` / `TierRouter`, a no-AWS
  example, and a sweep tool to tune it from your own traffic.
- **Communication:** the v1 → v2 story (the gate couldn't judge code or maths; the router's
  P(large) could) and the trade-off chart. Lead with it in the video.
