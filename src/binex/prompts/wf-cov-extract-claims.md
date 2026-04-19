You are extracting all verifiable factual claims from a response for independent verification.

Instructions:
1. Read the response carefully
2. Identify every statement that makes a factual claim (dates, numbers, names, causal relationships, statistics)
3. Express each claim as a simple, atomic statement that can be verified independently
4. Exclude opinions, recommendations, and subjective statements — only extract verifiable facts

Output format:
**Factual claims**:
1. [Atomic factual claim — one fact per line]
2. [Atomic factual claim]
3. [Atomic factual claim]
(continue for all claims)

**Total claims**: [N]

Rules:
- One claim per line — do not bundle facts
- Write each claim as a complete standalone statement (not "this" or "it")
- Include the source sentence in brackets if useful: [From: "..."]
- If a claim is already hedged in the text ("approximately"), preserve the hedge
