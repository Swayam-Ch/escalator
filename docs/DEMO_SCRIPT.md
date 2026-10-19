# Demo video script (target 2:45, hard limit 3:00)

Record a terminal split: left `strands-decider serve`, right `escalator`. Use a large font.

| Time | Screen | Say |
| --- | --- | --- |
| 0:00–0:20 | Title card: "Escalator: pay for the big model only when you have to" | "Most questions people ask an AI assistant are easy, yet we send all of them to the most expensive model. Escalator lets a 2-billion-parameter decision model, Strands Decider 2B, decide when that's actually needed." |
| 0:20–0:45 | The mermaid diagram from the README | "Every turn has two decisions. First, *route*: small model, large model, or ask the user? Second, if the small model answered, *gate*: is that draft good enough to ship? The decider returns calibrated numbers, and plain Python turns them into actions." |
| 0:45–1:05 | `escalator`, ask "What is the capital of Australia?" | "An easy one. Routed small, the gate scores it fully-answered at 0.97, and it ships for a fraction of a cent. The decider took about 150 milliseconds and costs nothing, because it runs locally." |
| 1:05–1:30 | Ask the bat-and-ball discount question | "A tricky math question. The router is confident this needs the expert model, so it goes straight to Sonnet and skips the cheap draft entirely." |
| 1:30–1:50 | Ask "Can you fix it?" | "No context at all. Instead of guessing, the router picks clarify, and the agent asks what you want fixed." |
| 1:50–2:10 | Ask the chmod 777 question | "The small model might answer this, but the gate flags it high-stakes, so it escalates. Mistakes here are expensive." |
| 2:10–2:35 | `bench/results/.../summary.md` table | "On our 36-question benchmark, Escalator cut LLM cost by **X%** and median latency by **Y%** versus always using the large model, and the judge rated **N of M** shipped small-model answers as good as the large model's." |
| 2:35–2:50 | `patterns.py` in the editor | "The pattern is one file with no dependencies: a router, a gate, and a policy you can tune. Drop it into any Strands agent. Link's below." |
