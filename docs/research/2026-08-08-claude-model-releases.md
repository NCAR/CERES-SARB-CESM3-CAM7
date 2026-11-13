# Claude model releases: late 2025 – August 2026

Date: 2026-08-08
Method: deep-research workflow (5 Sonnet search agents + 8 deep-reads), then
cross-checked at Fable level against Anthropic's API reference (model IDs,
pricing, effort/fast-mode facts verified; dates from anthropic.com/news and
press). Confidence noted where sources were secondary.

## Release timeline

| Date | Model | ID | Headline |
|---|---|---|---|
| 2025-09-29 | Claude Sonnet 4.5 | `claude-sonnet-4-5-20250929` | "Best coding model in the world"; SWE-bench Verified 77.2% |
| 2025-10-15 | Claude Haiku 4.5 | `claude-haiku-4-5-20251001` | Near-Sonnet-4 coding at 1/3 cost, 2–5× speed |
| 2025-11-24 | Claude Opus 4.5 | `claude-opus-4-5-20251101` | SWE-bench Verified 80.9%; price cut $15/$75 → $5/$25 |
| 2026-02-05 | Claude Opus 4.6 | `claude-opus-4-6` | "Agent teams" multi-agent coordination; 1M context *(medium conf.)* |
| 2026-02-17 | Claude Sonnet 4.6 | `claude-sonnet-4-6` | Default for Free/Pro; "Opus-class" framing *(medium conf.)* |
| 2026-04-16 | Claude Opus 4.7 | `claude-opus-4-7` | ~13% coding lift; new tokenizer; high-res vision (2576px); `xhigh` effort added *(medium conf.)* |
| 2026-05-28 | Claude Opus 4.8 | `claude-opus-4-8` | Dynamic-workflow tool; press framed as prep for "Mythos-class" |
| 2026-06-09 | **Claude Fable 5 / Mythos 5** | `claude-fable-5` / `claude-mythos-5` | First Mythos-class release — new tier above Opus |
| 2026-06-30 | Claude Sonnet 5 | `claude-sonnet-5` | "Most agentic Sonnet"; close to Opus 4.8 at lower cost |
| 2026-07-24 | Claude Opus 5 | `claude-opus-5` | Near-Fable intelligence at half the price; ARC-AGI-3 ~3× next best |

Model-ID convention: date-suffixed through the 4.5 generation; dateless pinned
snapshots from 4.6 onward (verified against the current API model table).

## The Fable/Mythos story (2026)

- **2026-03-26 / 04-07** — Mythos leaks via draft blog posts; Anthropic
  discloses it alongside **Project Glasswing** (defensive-cybersecurity
  consortium: AWS, Apple, Google, Microsoft, NVIDIA, JPMorganChase, et al.).
  `claude-mythos-preview` is invitation-only; by June ~150 orgs in 15+
  countries; partners report 10,000+ high/critical vulnerabilities found.
- **2026-06-09** — Fable 5 (GA) and Mythos 5 (Glasswing-only) launch. Same
  underlying model: Fable adds safety classifiers that can decline requests
  (`stop_reason: "refusal"`, categories incl. cyber/bio/reasoning-extraction,
  <5% of sessions), with server-side fallback routing to Opus. Mythos omits
  the classifiers.
- **2026-06-12 → 07-01** — US export-control order suspends both models
  (real-time nationality verification Anthropic couldn't perform); an Amazon
  researchers' jailbreak eliciting vulnerability detail was a related trigger.
  US orgs regain Mythos 5 on 06-26; controls lifted 06-30; global
  redeployment 07-01. Anthropic's follow-up testing found other frontier
  models could produce the same content. *(medium confidence on details)*

## Tier system and pricing (verified, as of 2026-08-08)

| Tier | Current model | $/MTok in/out | Positioning |
|---|---|---|---|
| Haiku | Haiku 4.5 | $1 / $5 | Quick answers, summaries, simple extraction |
| Sonnet | Sonnet 5 | $2/$10 intro to 08-31, then $3/$15 | Versatile default; "pick this if unsure" |
| Opus | Opus 5 | $5 / $25 | Deep research, complex reasoning, production agents |
| **Mythos-class** | Fable 5 (GA) / Mythos 5 (Glasswing) | $10 / $50 | Long multi-step projects, critical accuracy; 30-day retention required, no ZDR |

- All current models: 1M context, 128K max output (Haiku 4.5: 200K / 64K).
- **Effort parameter**: `output_config.effort` — introduced with `low/medium/
  high` on Opus 4.5 (Nov 2025), `max` added in the 4.6 generation, `xhigh`
  added with Opus 4.7; Opus 5, Sonnet 5, and Fable 5 support all five levels.
  (The launch-press claim that Opus 5 "introduced" effort is wrong.)
- **Fast mode**: research preview on Opus 5 and Opus 4.8 only (Claude API
  only); 2× price ($10/$50 on Opus 5) for up to ~2.5× output speed.
- Opus 4.1 deprecated, retires 2026-08-05; Sonnet 3.7 / Haiku 3.5 retired
  2026-02-19.

## Talk-relevant beats

- Three tiers → four: the Mythos-class tier (June 2026) formalizes
  "capability matched to consequence" — the /model + /effort slide's thesis.
- Effort became a first-class dial the same period (`xhigh` default in Claude
  Code for coding/agentic work).
- Cadence: Anthropic shipped 4 frontier releases in the 7 weeks Jun 9–Jul 24.
