# Artificial Analysis Intelligence Index — values for the AI Models timeline

Date: 2026-08-08
Method: web search + page fetch. Primary source: BenchLM's AAII leaderboard
snapshot of 2026-08-07 (168 models); Sonnet 4.5 / Haiku 4.5 from AA model
pages (reasoning config), consistent with the BenchLM scale (BenchLM
Sonnet 4.6 35.9 ≈ AA Sonnet 4.6 high 36).

The AA Intelligence Index is a versioned composite (v4.1 incorporates 9
evals: GDPval-AA v2, tau3-Banking, Terminal-Bench v2.1, SciCode, HLE, GPQA
Diamond, CritPt, AA-Omniscience, AA-LCR). Scores shift 1–2 points between
index versions (AA's own v4.1.1 of 2026-08-06 lists Opus 5 at 63); the deck
plots ONE snapshot (BenchLM 2026-08-07) for internal consistency.

## Chart policy

- Best config per model (Thinking / Adaptive where applicable) — matches
  AA's own frontier chart convention.
- y-axis mapping in 02-problem.tex: y = (AAII − 25) × 0.13.
- Astra has no AAII (unreleased); its chart height is a projection.

## Values plotted (slide "AI Models")

| Model | AAII | Config note |
|---|---:|---|
| Claude Opus 5 | 60.7 | #1 |
| Claude Fable 5 | 59.9 | |
| GPT-5.6 Sol | 58.9 | |
| Claude Opus 4.8 | 55.7 | |
| GPT-5.6 Terra | 55.0 | |
| GPT-5.5 | 54.8 | |
| Claude Opus 4.7 | 53.5 | Adaptive |
| Claude Sonnet 5 | 53.4 | |
| GPT-5.4 | 51.4 | |
| GPT-5.6 Luna | 51.2 | |
| GPT-5.3 Codex | 44.3 | |
| Claude Opus 4.6 | 43.7 | Adaptive |
| GPT-5.2 | 42.2 | |
| Claude Opus 4.5 | 40.8 | Thinking |
| GPT-5.1 | 36.9 | |
| Claude Sonnet 4.5 | 36 | AA page, reasoning |
| Claude Haiku 4.5 | 30 | AA page, reasoning |
| Gemini 3.1 Pro | 46.5 | table only, not plotted |

## Gemini 3.1 Pro benchmark fills (supplemental table)

SWE-bench Verified 80.6; ARC-AGI-2 77.1; OSWorld-Verified 76.2;
GPQA Diamond ~95.5 (vals.ai, prior research note); HLE no-tools 44.7
(Wikipedia table, prior research note). Terminal-Bench: 68.5 is on
version 2.0 — NOT entered in the 2.1 row. SWE-bench Pro: no figure found.

Sources: benchlm.ai/benchmarks/artificialanalysis;
artificialanalysis.ai model comparison pages;
nxcode.io / digitalapplied.com / datacamp.com Gemini 3.1 guides;
see also 2026-08-08-model-benchmarks.md.
