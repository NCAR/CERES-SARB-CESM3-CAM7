# OpenAI / Codex model releases: late 2025 – August 2026

Date: 2026-08-08
Method: deep-research workflow (Sonnet searchers + deep-reads); openai.com
blocks automated fetches, so official-page claims rest on search snippets and
reputable press — confidence flagged accordingly.

## Release timeline

| Date | Model | Notes |
|---|---|---|
| 2025-11-12 | GPT-5.1 (3 models; +2 on 11-19) | |
| 2025-11-19 | GPT-5.1-Codex-Max | First model natively trained for multi-context-window work via "compaction"; became Codex default same day |
| 2025-12-11 | GPT-5.2 (instant/thinking/pro) | Accelerated after Altman's internal "code red" (12-01) over Gemini 3 |
| 2025-12-18 | GPT-5.2-Codex | Long-horizon compaction, project-scale refactors |
| 2026-02-05 | GPT-5.3-Codex | ~25% faster; Pro-only at launch; Spark research-preview variant 02-12 |
| 2026-03-05 | GPT-5.4 (Thinking/Pro) | Native computer use; 1M context; tool-search cutting tool-token cost 47%; mini/nano 03-17 |
| 2026-04-23 | GPT-5.5 (codename "Spud") | Instant became free-tier default 05-05 |
| 2026-06-26 | GPT-5.6 Sol limited preview | In ChatGPT and Codex |
| 2026-07-09 | **GPT-5.6 family GA** | After a government security review; Sol / Terra / Luna tiers |

## Luna, Terra, Sol — what they are

**Not separate models or codenames: they are OpenAI's three "durable
capability tiers," introduced with GPT-5.6 (GA 2026-07-09).** The version
number identifies the generation; the tier names are meant to persist across
generations and "advance on their own cadence" — structurally the same move
as Anthropic's Haiku/Sonnet/Opus (+Fable) naming.

| Tier | Model ID | $/MTok in/out | Positioning |
|---|---|---|---|
| **Sol** | `gpt-5.6-sol` | $5 / $30 | Flagship; the Codex coding/agentic workhorse (no separate "5.6-Codex" model — Sol is it) |
| **Terra** | `gpt-5.6-terra` | $2.50 / $15 | Mid-tier; ~GPT-5.5 capability at half the cost |
| **Luna** | `gpt-5.6-luna` | $1 / $6 | Fastest/cheapest |

Bare `gpt-5.6` routes to Sol. Family specs (secondary source): knowledge
cutoff 2026-02-16, 1M context, 128K max output. Pricing is medium-confidence
(snippet-derived; openai.com unfetchable).

## Tier-naming comparison (talk-relevant)

| | Anthropic | OpenAI |
|---|---|---|
| Tiers | Haiku / Sonnet / Opus / **Fable (Mythos-class)** | Luna / Terra / Sol |
| Scheme | Tier name + generation number (Sonnet 5) | Generation number + tier name (GPT-5.6 Sol) |
| Introduced | Haiku/Sonnet/Opus Mar 2023; Fable Jun 2026 | Jul 2026 (GPT-5.6) |
| Top-tier access | Fable GA with safety classifiers; Mythos gated (Glasswing) | Sol generally available |

Both vendors converged in mid-2026 on the same idea the talk's /model +
/effort slide makes: a stable capability ladder you pick from per task, with
the generation advancing underneath.

## Codex CLI cadence note

Codex-branded system-card models shipped per generation (5.1-Codex-Max,
5.2-Codex, 5.3-Codex) until 5.6, where the flagship tier absorbed the coding
role (Sol: ~8-pt FuncPass, ~2-pt SecPass over GPT-5.4 on Codex evals —
low-confidence, from developers.openai.com snippets).
