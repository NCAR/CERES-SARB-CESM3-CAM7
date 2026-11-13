# Slide command badges — design

Date: 2026-08-06
Status: approved mapping; slides to be revised one at a time with review

## Goal

Emphasize one Claude Code slash command per slide across the first set of
slides (and slide 15), so the talk shows the workflow as the audience would
actually type it. The 16-slide / 15-minute arc in `slides/outline.md` is
unchanged.

## Non-goals

- No reordering, adding, or removing slides.
- Slides 10–14 and 16 keep no badge (CERES-MIP ran no commands yet; the
  comparison and takeaway stay conceptual).
- No poster-banner mode; the deck builds in plain 16-page mode (which also
  keeps the free 4×4 poster tiling valid).

## Command inventory (verified)

All badge commands are built-ins in current Claude Code (verified against
v2.1.223 docs and changelog): `/model`, `/effort`, `/plugins`,
`/deep-research`, `/plan`, `/init`, `/memory`, `/skills`, `/loop`, `/goal`,
`/permissions`, `/hooks`. Brainstorming is plugin-provided:
`/superpowers:brainstorming`, installed via `/plugins`.

## Locked mapping and taglines

| Slide | Command(s) | Badge tagline |
|---|---|---|
| 02-problem | `/model` + `/effort` | match capability and reasoning depth to the consequence of the task |
| 03-definition | `/plugins` → `/superpowers` | turn intent into a spec through structured dialogue, before any code. Slide carries a box ranking the superpowers skills by importance to this project (2026-08-08 review round) |
| 04-loop | full rail | `/deep-research → /superpowers:brainstorming → /plan → /skills → /loop → /goal` — the loop as you actually type it |
| 05-cam7-starting-point | `/deep-research` | parallel forensic reading, condensed into one citable synthesis |
| 06-cam7-spec | `/plan` | turn the frozen contract into bounded plans agents execute independently |
| 07-agentic-control-plane | `/init` + `/memory` | the control plane is written and maintained from inside the session, not around it |
| 08-project-skills | `/skills` | package recurring stages as bounded procedures with guardrails and handoffs |
| 09-evidence-handoffs | `/loop` + `/goal` | the monitor advances run state; the goal refuses to stop before the gates pass |
| 15-operating-protocol | `/permissions` + `/hooks` | decision authority the harness enforces, not just prose the agent obeys |

Slide 4 is the deliberate exception to one-per-slide: its loop diagram nodes
are labeled with the commands (evidence `/deep-research`, decisions
`/superpowers:brainstorming`, contracts `/plan`, executable tasks `/skills`,
tests and runs `/loop`, acceptance `/goal`), making it the roadmap the later
slides zoom into.

## Badge format

- Last visible content line of each badged slide:
  `` **`/command`** — tagline `` (bold command, em-dash, one line).
- Each badged slide's `Visual:` comment notes the corner-badge intent: same
  position on every slide, terminal-style chip.
- Each badged slide's speaker note gains one sentence on what to say about
  the command. Slide 2's note carries the model-tier and reasoning-depth
  talking points; slide 15's note carries the contrast between policy as
  prose today (CLAUDE.md account isolation; `settings.local.json` holds a
  single allow rule) and harness enforcement tomorrow (deny rules for
  cross-account paths, a PreToolUse hook gating `case.submit`).

## File changes

- `slides/02-problem.md`, `03-definition.md`, `04-loop.md`,
  `05-cam7-starting-point.md`, `06-cam7-spec.md`,
  `07-agentic-control-plane.md`, `08-project-skills.md`,
  `09-evidence-handoffs.md`, `15-operating-protocol.md`: add badge line,
  speaker-note sentence, and visual note.
- `slides/outline.md`: add a Command column to the timing table; add the
  badge motif to the visual-development pass.

## PDF deck (parallel build)

- The rendered deck lives at `~/DavidFillmore/Media/decks/intent_to_evidence`,
  copied from `templates/ncar_teal` per the Media repo's conventions, built
  with `scripts/build.sh` (Tectonic; gates: no overfull pages, 16 pages).
- `meta.tex`: title "From Intent to Evidence", plain mode
  (`\posterbannerfalse`); the 16 slide files are renamed to the talk slugs
  used in this repo's `slides/`.
- Theme mixing: the deck stays ncar_teal (Helvetica deck-wide). The command
  badge chip renders in Claude clay (#D97757) on every badged slide. Slides
  3, 4, and 15 — the slides about the agentic method itself — additionally
  get full clay treatment via a deck-local scoped switch that re-binds
  `accent`/`accentSoft`/`accentDeep` and `\themelogo` for that slide only.
  Science/case slides keep NCAR teal. Per-slide adjustments allowed during
  review.
- The markdown files in `slides/` remain the content source of truth; the
  deck is the rendering.

## Execution protocol

Generate one slide revision at a time, in deck order, starting with slide 2.
For each slide: revise the markdown here, port it to the deck's `.tex` file,
rebuild the PDF green, and present both. The user reviews each slide before
the next is touched.

The rendered deck contains exactly the slides reviewed so far: `main.tex`
uncomments one `\input` per round, so the PDF grows slide by slide. While
the deck is partial, it is built with `tectonic --keep-logs main.tex`
directly; `build.sh`'s 16-page gate and the 4×4 poster tiling apply only
once all 16 slides are in. Tagline or mapping
changes discovered during review are applied to this document in the same
commit as the slide they affect.

## Acceptance

- Every badged slide still reads as one idea; the badge is one line.
- Command names match current Claude Code spelling exactly.
- `outline.md` and the slide files agree on the mapping.
