# Frontier-model benchmarks as of August 2026

Date: 2026-08-08
Method: deep-research workflow + Fable-level review. Benchmark numbers vary
by tracker, question subset, tool access, and effort config — every figure
below carries its source and config. Single-number citations without config
are unreliable; that variance is itself a talk-worthy point.

## Humanity's Last Exam (HLE) — general intelligence

- **What**: 2,500 expert-level closed-ended questions across 100+ subjects;
  Center for AI Safety (Dan Hendrycks) + Scale AI; ~1,000 contributors from
  500+ institutions. Finalized 2025-04-03; HLE-Rolling (continuously updated)
  since 2025-10-08; published in Nature (vol. 649, 2026-01-28,
  DOI 10.1038/s41586-025-09962-4).
- **Not to be confused with** "Agents' Last Exam" (ALE) — a professional-
  workflow agent benchmark. OpenAI's "53.6" figure for GPT-5.6 Sol is an ALE
  score, and press often conflates the two. (ALE's attribution itself is
  muddled across sources — Snorkel AI leaderboard vs. a UC Berkeley RDI
  paper; unresolved, low priority.)

### Score history (text-only unless noted)

| Date | Leader | Score | Source/config |
|---|---|---|---|
| early 2026 | Gemini 3 Pro Preview | ~37.5% | low conf. |
| 2026-02-19 | Gemini 3.1 Pro Preview | 44.4% | Artificial Analysis |
| 2026-08-03 | Claude Fable 5 | 53.3% | Wikipedia table (GPT-5.6 Sol 47.2%, Muse Spark 1.1 45.1%, Gemini 3.1 44.7%) |
| 2026-08-07 | Claude Fable 5 (adaptive, max effort, Opus 4.8 fallback) | **55.5%** | Artificial Analysis, 2,158-q subset, pass@1; #2 Opus 5 max 54.9% |
| 2026-08-07 | with tools | Opus 5 64.7%, Mythos 5 64.5% | BenchLM; matches Anthropic's own 64.7% claim |

Tools vs. no-tools gap is ~10–20 points on the same model. Same-model spread
across trackers (Fable 5: 53.3–55.5 no-tools) comes from differing subsets
and configs.

## Coding

| Benchmark | Standing (Aug 2026) | Source/notes |
|---|---|---|
| SWE-bench Verified | Opus 5 ~97.0% > GPT-5.6 Sol ~96.2% > Fable 5 ~95.0% > Opus 4.8 ~88.6% | vals.ai; near-saturated at the frontier |
| SWE-bench Pro | Fable 5 ~80% vs GPT-5.6 Sol ~64.6% | morphllm leaderboard; OpenAI de-emphasized Verified for Pro in early 2026 (contamination concerns), then questioned Pro's reliability when it trailed — low conf., contested |
| Artificial Analysis Coding Agent Index v1.1 | GPT-5.6 Sol (max reasoning) 80, ~2.8 pts above Fable 5, at ~1/3 less cost | conflicting with SWE-bench Pro ordering — no single benchmark tells the story |

Historical anchors: Sonnet 4.5 77.2% (Sep 2025) → Opus 4.5 80.9% (Nov 2025)
→ ~97% frontier (mid-2026): Verified effectively saturated in ~9 months.

## Agentic / computer use / reasoning

| Benchmark | What it measures | Standing | Source |
|---|---|---|---|
| Terminal-Bench 2.1 | Terminal/agentic tasks | GPT-5.6 Sol (xhigh) ~89.5% ≈ Opus 5 (max) ~89.1%; 2–5 pt spread across trackers | tbench.ai, low conf. |
| FrontierBench v0.1 | 74-task successor to Terminal-Bench | Opus 5 43.3% (max) — new, unsaturated | Anthropic launch card |
| OSWorld-Verified | Computer use (361 tasks, pass@1) | Fable/Mythos 5 ~85.0%, above ~72.4% human baseline; GPT-5.6 Sol 62.6% but on harder OSWorld 2.0 — not comparable | Anthropic system card / steel.dev |
| ARC-AGI-2 | Abstract reasoning | GPT-5.6 Sol ~92.5%, Opus 5 ~90.4% | BenchLM aggregator, low conf. |
| ARC-AGI-3 | Successor, emerging 2026 standard | Opus 5 ~3× next-best (30.2% per secondary sources) | Anthropic launch card |
| GPQA Diamond | Graduate-level science QA | Gemini 3.1 ~95.5% ≈ GPT-5.6 Sol ~95.2% > Opus 5 ~93.4% — saturated | vals.ai |
| tau2-bench | Tool-agent conversations | topped by GLM-5.x models (~99%); Claude/OpenAI figures unconfirmed — research gap | Sierra leaderboard, low conf. |

## Takeaways for the talk

1. **Benchmarks saturate fast**: SWE-bench Verified went 77% → 97% in 11
   months; GPQA is saturated; the field keeps minting harder successors
   (FrontierBench, ARC-AGI-3, HLE-Rolling).
2. **Rankings flip across benchmarks**: Fable 5 leads HLE and SWE-bench Pro;
   GPT-5.6 Sol leads ARC-AGI-2 and the AA coding index; Opus 5 leads
   SWE-bench Verified. Model choice is task-dependent — the /model + /effort
   thesis.
3. **Config dominates single numbers**: tools vs. no-tools moves HLE by
   10–20 points; effort level moves most agentic scores; any quoted score
   needs benchmark + config + date.
