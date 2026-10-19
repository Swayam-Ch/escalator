# Demo video script (target 2:45, hard limit 3:00)

Record a terminal split: left `strands-decider serve`, right `escalator`. Use a large font. The
decider takes a few seconds per decision on a laptop, so cut the waiting in editing and say so
once on screen.

| Time | Screen | Say |
| --- | --- | --- |
| 0:00–0:20 | Title card: "Escalator: pay for the big model only when you have to" | "Most questions people ask an AI assistant are easy, yet we send all of them to the expensive model. Escalator lets a 2-billion-parameter decision model, Strands Decider 2B, decide when that's actually needed." |
| 0:20–0:45 | The mermaid diagram from the README | "Every turn has two decisions. First, *route*: small model, large model, or ask the user? Second, if the small model answered, *gate*: is that draft good enough to ship? The decider returns calibrated numbers, and plain Python turns them into actions." |
| 0:45–1:05 | `escalator`, ask "What is the capital of Australia?" | "An easy one. The router gives 'needs the large model' a low probability, so Nova Micro answers, the gate accepts it, and it ships for a fraction of a cent. The decider runs locally and costs nothing." |
| 1:05–1:25 | Ask the bat-and-ball discount question | "A tricky maths question. The router's probability is above 0.82, so it goes straight to Claude Haiku and skips the cheap draft." |
| 1:25–1:40 | Ask "Is this a good price?" | "No context at all. Instead of guessing, the router picks clarify, and the agent asks what you mean." |
| 1:40–2:15 | `bench/reported` summaries, then the sweep table | "Version one saved 68%, but shipped four bad answers: code, SQL and maths. The gate couldn't tell they were wrong; a 2B classifier can't run code. But the router's probability had already separated easy from hard. I replayed the run at every threshold and picked 0.82. Version two: zero answers worse than the baseline, and every easy question 99% cheaper. On 24 questions it had never seen, it saved 32%, but three answers slipped through, two of them code and tax, so that's where I'd go next." |
| 2:15–2:35 | `patterns.py` in the editor | "The pattern is one file with no dependencies: a router, a gate, and a policy you tune from data. Drop it into any Strands agent. Link's below." |
