# Deck review — *Spec-Driven Scientific Workflows with Coding Agents*

**Deck under review:** `~/DavidFillmore/Media/decks/agentic_ai` (17 slide files, 23 pages,
`main.pdf` built 2026-08-09 23:24)
**Talk:** IMPACT group, NSF NCAR / CISL — their regular monthly group meeting, 2026-08-12,
15 minutes

> ### Audience brief — corrected 2026-08-10, and it invalidates some of what follows
>
> David's words: *"the whole point of the deck is to illustrate the **features of the agents**,
> and **how I personally have been using them**. It is not to hand off an agentic CESM system.
> CESM is just an example of a recent project of mine."*
>
> The room is **people already using AI agents, with a wide range of familiarity and skill** —
> peers at a monthly group meeting, not sceptics needing convincing. **Nobody has access to
> `CERES-SARB-CAM7`**; it is an early project, so repo internals are illustration, never
> evidence.
>
> **What this invalidates in this document.** The narrative dimension's audience calibration
> assumed a room of Earth-system modellers ready to challenge the science, and the gaps section
> partly followed it. Specifically: the "hostile CAM maintainer" framing was invented; [S2](#s2)
> was justified by "someone who clones the repo and types this gets nothing", which is false;
> and the judgment in [§8](#8-pacing--18-pages-in-15-minutes) that the Attention frame sits
> "below the room's level" was calibrated to the wrong audience — for people *using* these
> tools, how the context window works is on-topic.
>
> **What it does not touch.** Every factual finding stands, and matters *more* than it would
> have: when the subject of the talk is agent features, a badge naming a removed command or a
> tool chip for a tool that does not exist is a worse error than a wrong aerosol number.
**Review date:** 2026-08-09 / 2026-08-10 · **revised** 2026-08-10 with two rounds of fixes
applied — see [Status](#status--what-has-been-applied)
**Method:** 21 agents — 3 URL verifiers (all 27 links fetched individually), 8 audit
dimensions each paired with an adversarial verifier that had to refute the findings before
they survived, then synthesis plus a completeness critic. 67 findings survived verification.
The highest-stakes items were then re-checked by hand (see
[Appendix A](#appendix-a--independently-re-verified)).

Slide 14 (Lessons) is empty by design and was excluded from defect reporting; a proposal for
its content is in [§7](#7-lessons-slide-slide-14--proposal).

---

## Verdict

The deck is in good shape. No dead links, no 404s, and the `.tex` comments already anticipate
most of what a reviewer would raise — several findings below are the deck's own TODOs coming
due rather than oversights.

The real exposure is concentrated in four places:

1. **Page 3, the one quantitative slide.** Its source link points at a different
   organisation publishing a different metric, and the metric's name is missing a word — on
   page 3 and again in the appendix. An audience member who follows the link cannot find a
   single plotted number.
2. **Three command/skill labels present things as typeable that no longer are** — `/agents`
   is a removal stub in the installed CLI, `/superpowers` is not a command, and the three
   project-skill chips are not on Claude Code's skill search path in this repo.
3. **One number contradicted by a repo the same slide links** — `~1000` Pydantic fields
   against a measured 336.
4. **Pacing is tight but workable.** The spoken run is pages 1–18 (through Lessons); 19–23 are
   supplemental. That is ~50 s/page, with four pages carrying well over that — see
   [§8](#8-pacing--18-pages-in-15-minutes).

Everything else is clarity, consistency and bookkeeping.

---

## Status — what has been applied

Two rounds of fixes have landed in the deck. **The findings below keep their original review
text**; this table is the record of what was done about each.

| # | Item | Status | Where |
|---|---|---|---|
| [M1](#m1) | p3 source link → `benchlm.ai/benchmarks/artificialanalysis` | ✅ **fixed** | Media `1c69c66` |
| [M2](#m2) | p3 y-axis → *Artificial Analysis / Intelligence Index* (2 lines) | ✅ **fixed** | Media `1c69c66` |
| [M3](#m3) | p23 row → `AA Intelligence Index`, AA added to legend | ✅ **fixed** | Media `1c69c66` |
| [M4](#m4) | p23 HLE row `$^{*}$` + source-split footnote | ✅ **fixed** | round 2 |
| [M5](#m5) | p6 `~1000` Pydantic fields | ⏸️ **kept as-is** — aspirational, David's call | — |
| [M6](#m6) | p10 `D5 dry mixing-ratio scaling` → `D4 mass + number scaling` | ✅ **fixed** | round 2 |
| [M7](#m7) | p11 badge → `/subtask` | ✅ **fixed** | Media `1c69c66` |
| [M8](#m8) | p5 badge → `/plugins → superpowers` | ✅ **fixed** | Media `1c69c66` |
| [M9](#m9) | p21 docs link target → `code.claude.com/docs` | ✅ **fixed** | round 2 |
| [M10](#m10) | p3 `5.3` → `5.3 / Codex` | ✅ **fixed** (revised remedy, see below) | round 2 |
| [S3](#s3) | "Milestone 3" not in the repo | ❌ **withdrawn** — deliberate fiction | — |
| [A1](#a1) | p1 affiliation missing "NSF" | ⛔ **declined** — see below | — |
| [A2](#a2) | clay sidebar contrast | ✅ **fixed**, measured 5.60:1 | round 2 |
| [P1](#p1)–[P3](#p3) | bubble collisions | ✅ **fixed** — but *not* by the proposed remedies, see [§9](#9-bubble-consistency-pass-2026-08-10) | round 3 |
| [P4](#p4) | conda mark fused with the block bar | ⏸️ **open** — the fix is positional, not chromatic | — |
| [P5](#p5) | `80` → `80.0` | ✅ **fixed** | round 3 |
| [P6](#p6) | "NASA Earth Data" → "Earthdata" | ⏸️ **open** | — |
| [P7](#p7) | continuation frame titles qualified | ✅ **fixed** | round 3 |
| [P8](#p8) | quote subject restored | ✅ **fixed** — costs one line + 2.88 pt vbox, nothing clipped | round 3 |
| [P9](#p9)–[P11](#p11) | mirror chrome, outline, footers | ✅ **fixed** | round 4 |
| [P13](#p13) | stale comments | ✅ **partly fixed** — 05, 09, 16, 17 done | round 3 |
| [S12](#s12) | `main.tex` badge-mapping citation | ⏸️ **open** | — |
| — | bubble consistency deck-wide | ✅ **done** | [§9](#9-bubble-consistency-pass-2026-08-10) |
| [S2](#s2) | skill chips not on the skill search path | ✅ **fixed in the repo, not the slide** — see below | round 5 |
| [S5](#s5) | five bars against four arcs (p20) | ✅ **fixed** | round 5 |
| [S9](#s9) | hooks claimed as enforced | ✅ **fixed** | round 5 |
| [A4](#a4) | `python` chip names a tool that does not exist | ✅ **fixed** → `read` | round 5 |
| [S1](#s1) / Gap 1 | spec-driven thesis never stated until p11 | ⏸️ **open** | — |
| [S4](#s4) | `ultracode` unglossed on the load-bearing slide | ⏸️ **open** — clarity call in David's own vocabulary, both remedies cost something | — |
| §7 | Lessons slide (p18) | ✍️ **David is writing it** | — |

Everything else in this document is **open**. Colour findings are closed at David's direction —
the deck is built from templates and the palette is settled; [A2](#a2) was a template-seam bug
(`\claudeslide` missing what `\nasaslide` already had) and is fixed.

### Three notes where the applied fix differs from what was proposed

**M4 — the legend is now four lines, and it fits.** The proposed footnote was predicted to
spill the acronym legend from three lines to four and possibly overflow the block. It did go to
four lines, but the rebuild shows white space still under the block: no vbox overflow. The
`$^{*}$` widens column 1 by ~2.4 pt, which grew the tabular's **pre-existing** hbox overhang
from ~18.5 pt to 2.5 pt reported at `17-benchmarks:54`. Nothing crosses the frame edge. Final
footnote wording: `$^{*}$Fable 5 / Opus 5: AA 2,158-q subset; Sol / Gemini: 2026-08-03 table`.

**M10 — the one-line remedy was wrong; it is set on two lines instead.** The review proposed
`{5.3 Codex}` in place, having checked the neighbouring *labels and dots* for collisions. Both
the editing agent and the verifier independently measured that the widened one-line label runs
its right end straight through the **black OpenAI polyline** — the very line it annotates — and
clips the clay Anthropic line behind it. TikZ nodes have no fill, so nothing would mask the
strike-through. Applied instead:

```latex
\node[above, align=center, font=\scriptsize] at (4.95,2.63) {5.3\\Codex};
```

Two lines grow the label upward, away from the crossing; the 0.15-unit nudge left keeps the
right edge clear of the black segment while the label stays beside its own dot (a smaller
offset than `Opus 4.5` already carries). Verified on the rebuild. The picture did not widen —
`03`'s Overfull hbox is unchanged at 28.46 pt.

**A1 — declined 2026-08-10 at David's direction.** The fix cannot be made inside `meta.tex`:
adding "NSF " grows the centred institute line 12.42 pt per side, and the measured ink gap to
the ChatGPT knot on the title slide is 13.4 pt, so the renamed line would clear by ~1 pt and
consume the clearance `01-title.tex`'s own comment records as deliberate. The options offered
were to shrink the ChatGPT mark to 2.45 cm (which would also have settled [A5](#a5)), to use
the short form "NSF NCAR", or to drop both vendor marks from page 1. **None taken — the
affiliation stays as it is.** The page-1 vs page-22 inconsistency is recorded here for a later
round; [A5](#a5) remains open and independent.

### S2 — fixed in the repo rather than on the slide

The three chips on page 13 are set in the deck's command-chip tokens, i.e. as things you can
type. They were not: Claude Code's project skill root is `cwd/.claude/skills`, and the three
skills lived only in `skills/` and `.agents/skills/`. Rather than de-emphasise the chips,
**the skills were symlinked into `.claude/skills/`** alongside `build-cesm-cam7`:

```
.claude/skills/preprocess-ceres-data -> ../../.agents/skills/preprocess-ceres-data
.claude/skills/configure-cesm3-runs  -> ../../skills/configure-cesm3-runs
.claude/skills/closeout-ceres-runs   -> ../../skills/closeout-ceres-runs
```

Confirmed working: all three now register as loadable skills in a live session. **Nothing on
the slide changed** — the chips are simply true as drawn, and a colleague who clones the repo
gets what the slide promises.

> Not done: `postprocess-ceres-davinci` is the fourth checked-in project skill and is still
> outside the skill root, so the root is now three-of-four complete. One more symlink would
> finish it. It is also [Gap 2](#gap-2--postprocess-ceres-davinci-is-invisible-in-all-23-pages).

### Slide 18 (Lessons) — David is writing it

Left to the author at his direction, 2026-08-10. The five candidates in [§7](#7-lessons-slide-slide-14--proposal)
stand as raw material, not a draft. **Until it is built the subtitle over-promises**: the deck
is titled *Lessons from the Community Earth System Model* and page 18 is blank.

### Mirror drift these fixes introduced

The `.tex` is the source of truth and `slides/*.md` mirror it, so the applied fixes have put
the mirrors out of date in four new places, on top of the pre-existing drift in
[P9](#p9)–[P11](#p11):

- `slides/03-ai-models.md` — the axis label, the source link, and the `5.3` point label
- `slides/05-plugins.md` — the badge is now `/plugins → superpowers`
- `slides/08-specs-planning.md:99` — still reads *D5 dry mixing-ratio scaling*
- `slides/09-development-test-cycles.md` — the badge is now `/subtask` alone
- `slides/17-benchmarks.md` — the row label, the AA legend entry, and the HLE footnote

Not actioned in either round. Worth folding into whichever batch clears P9–P11.

---

## 1. Link verification — all 27 URLs

Every URL was fetched individually and checked three ways: does it resolve, does the visible
text on the slide honestly represent the target, and is every date/title the deck asserts
about it true.

**Result: 24 ok · 3 mismatch · 0 broken · 0 dead.** The single unverifiable host
(`openai.com`, which 403s all automated clients — already noted in the `.tex`) was
corroborated through `openai.com/news/rss.xml`.

### Anthropic group — 7 ok, 1 mismatch

| URL | Verdict |
|---|---|
| `code.claude.com/docs/en/setup` | **mismatch** — see [M9](#m9) |
| `code.claude.com/docs/en/best-practices` | ok (200, canonical destination) |
| `anthropic.com/engineering` | ok |
| `anthropic.com/engineering/building-effective-agents` | ok — date 2024-12-19 correct |
| `anthropic.com/engineering/effective-context-engineering-for-ai-agents` | ok — 2025-09-29 correct |
| `anthropic.com/engineering/effective-harnesses-for-long-running-agents` | ok — 2025-11-26 correct |
| `anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills` | ok — 2025-10-16 correct |
| `anthropic.com/engineering/multi-agent-research-system` | ok — 2025-06-13 correct |

**All five asserted publication dates are exactly right.** The slide 06 quotation is verbatim
and correctly attached to *workflows* rather than agents — the source sentence is
"Workflows are systems where LLMs and tools are orchestrated through predefined code paths."

### OpenAI group — 6 ok, 1 mismatch, 1 unverifiable

| URL | Verdict |
|---|---|
| `arena.ai/leaderboard` | **mismatch** — see [M1](#m1) |
| `learn.chatgpt.com/docs` | ok — the `developers.openai.com/codex/*` → `learn.chatgpt.com/docs/*` 308 chain the `.tex` describes is confirmed |
| `learn.chatgpt.com/docs/codex/cli` | ok — page h1 is "Codex CLI" |
| `learn.chatgpt.com/docs/agent-configuration/agents-md` | ok |
| `openai.com/news/` | unverifiable by fetch (403 to all clients); RSS returns 200 with 1115 items |
| `openai.com/index/scientific-computing-agentic-ai` | ok — 2026-07-28 confirmed via RSS |
| `openai.com/index/codex-maxxing-long-running-work` | ok — 2026-06-22 confirmed via RSS |
| `openai.com/index/using-codex-to-simulate-black-holes/` | ok — 2026-06-11 confirmed; trailing-slash nit, [S11](#s11) |

**All three asserted post dates are exactly right**, and two of the three hrefs are
byte-identical to OpenAI's own canonical RSS `<link>`.

### Science / NCAR group — 8 ok, 1 title mismatch

| URL | Verdict |
|---|---|
| `ceres.larc.nasa.gov` | ok — expansion matches the site's own title verbatim |
| `data.giss.nasa.gov/CERESMIP/` | ok — confirmed the CERESMIP project page |
| `cesm.ucar.edu/models/cesm3` | ok — but see the caveat below |
| `earthdata.nasa.gov` | ok — brand is "Earthdata", one word ([P6](#p6)) |
| `github.com/NCAR/DAVINCI` | ok — public, Apache 2.0 |
| `arxiv.org/abs/1706.03762` | ok — Vaswani et al. 2017, *Attention Is All You Need*, title and year exact |
| `ncarprojects.ucar.edu/ai` | title mismatch — page spells the initialism out; **no edit recommended**, expanding the `\resitem` title grows it to three lines and pushes the entries below it down |
| `ncar-hpc-docs.readthedocs.io/en/latest/` | ok |
| `ncar-hpc-docs.readthedocs.io/en/latest/compute-systems/derecho/` | ok |

> **Awareness only, no action proposed.** The CESM3 page still describes CESM3 as forthcoming
> ("more information coming soon"), while slide 07's panel prints "We need to configure and
> run **CESM3**". Nothing on the slide is false — the prompt is a real prompt — but if anyone
> clicks through from the Resources frame during Q&A, that is what they will see.

---

## 2. Must fix

Wrong facts, misleading links, and numbers that contradict their own source. Each fix names
one element on one slide.

<a name="m1"></a>
### M1 · `slides/03-ai-models.tex:39` (page 3) — the source link points at the wrong organisation

The only source link on the deck's only quantitative slide,
`\decklink{https://arena.ai/leaderboard}{arena.ai/leaderboard}`, points at **Arena
Intelligence's** human-preference Elo leaderboard. It does not publish the Artificial
Analysis Intelligence Index; the phrase appears nowhere on the page. The deck's own
provenance (this file's comment, and `docs/research/2026-08-08-aa-intelligence-index.md`)
names `benchlm.ai/benchmarks/artificialanalysis`.

**Fix.** Change that one `\decklink` to:

```latex
\decklink{https://benchlm.ai/benchmarks/artificialanalysis}{benchlm.ai/artificialanalysis}
```

Verified by hand: that page carries the exact 2026-08-07 snapshot the chart plots — Opus 5
60.7, Fable 5 59.9, GPT-5.6 Sol 58.9. Node text only; nothing in the overlay moves.

> **Do not** substitute `artificialanalysis.ai/leaderboards/models`. It is the metric's home
> and is live, but its current v4.1.1 lists Opus 5 at 63 against the plotted 60.7, so the link
> would contradict the chart.

<a name="m2"></a>
### M2 · `slides/03-ai-models.tex:61–62` (page 3) — the y-axis names no index

The rotated axis label reads **"Artificial Intelligence Index"**. The metric is the
*Artificial Analysis* Intelligence Index — the file's own comment spells it correctly. As
rendered it is a generic phrase, and it collides with Stanford HAI's "AI Index". Combined
with M1, page 3 currently gives the audience no route to its own data.

**Fix.** Add `align=center` to that node and set the text to
`{Artificial Analysis\\Intelligence Index}`. Two lines are required — the one-line string
overruns the ~49 mm axis. No other node moves. (A one-liner "AA Intelligence Index" also
fits, but then AA needs defining, as in M3.)

<a name="m3"></a>
### M3 · `slides/17-benchmarks.tex:30` (page 23) — same misnaming in the appendix

The first table row is labelled "Artificial Intelligence Index", while the file's own comment
calls it "the AAII row". This is the page a sceptical listener opens to check the timeline.

**Fix.** Change the row label to `AA Intelligence Index` (shorter than the current text, so
column widths are unaffected) and append to the acronym legend:
`\;\textbullet\; \textbf{AA}: Artificial Analysis`. No cell values change.

<a name="m4"></a>
### M4 · `slides/17-benchmarks.tex:31` (page 23) — the HLE row mixes two trackers

Per `docs/research/2026-08-08-model-benchmarks.md`, Fable 5 55.5 and Opus 5 54.9 come from
Artificial Analysis' 2,158-question subset (2026-08-07); Sol 47.2 and Gemini 44.7 come from
the 2026-08-03 published table. The same doc warns the same-model spread is 53.3–55.5. On a
single tracker Sol's no-tools figure is higher (Fable 55.5 / Opus 54.9 / Sol 49.5), so **the
printed Anthropic-vs-OpenAI gap is inflated** — exactly what a benchmark-literate NCAR
audience will press on.

**Fix.** Keep all four values and mark the split. Row label →
`Humanity's Last Exam (no tools)$^{*}$`, and append to the legend:
`\;\textbullet\; $^{*}$Fable 5 / Opus 5: AA 2,158-q subset (2026-08-07); Sol / Gemini: 2026-08-03 published table`.

> **Do not** swap in 53.3 / 52.6 from a BenchLM AA-HLE page — BenchLM's HLE leaderboard is the
> *tools-assisted* view (Opus 5 64.7) and those values could not be corroborated.

<a name="m5"></a>
### M5 · `slides/06-reproducible-workflows.tex`, second `\item` (page 6) — `~1000` overstates by ~3×

`$\sim$1000 Pydantic-validated fields` sits two lines under a link to
`github.com/NCAR/DAVINCI`, so anyone can check it. **Re-measured by AST walk (confirmed by
hand): `davinci_monet/config/schema.py` has 336 annotated fields across 50 classes in 1995
lines**; every Pydantic-bearing module in the package totals ~421 fields / 66 classes.

The `.tex` comment already flags this as forward-looking and user-requested, and asks for a
re-measure before the talk. **The re-measure is now done and the number did not move.**

**Fix, your call since the figure was requested as aspirational.** Either
`hundreds of Pydantic-validated fields` (keeps the forward-looking framing) or `$\sim$350`
(measured). One bullet; nothing else on the slide changes.

<a name="m6"></a>
### M6 · `slides/08-specs-planning.tex:165`, node `d1` (page 10) — wrong decision number

The label reads `D5 dry mixing-ratio scaling`. `SPEC.md` makes **D5 the radiative-coupling
decision** (direct effect only; ACI hook present but off) — and this frame's own comment says
so ("D5 is the ACI hook"). The scaling decision is **D4**: uniform column rescale applied to
all aerosol species mass *and* number. Both bubbles feeding this row — "column scaling?" and
"mass or number?" — map to D4. The word "dry" occurs nowhere in `SPEC.md`, the SP2 plan, or
`CERES-MIP/fable/09-run-plan.md`; all three say "mass and number mixing ratios".

**Fix.** Change the `d1` node text to `D4 mass + number scaling`. Same column width; no other
node moves.

> Leave `d4` ("D8 tropospheric only") alone — `slides/08-specs-planning.md` records that it is
> numbered D8 at your direction because the decision originates in the CERESMIP run plan. That
> is an acknowledged choice, not an error.

<a name="m7"></a>
### M7 · `slides/09-development-test-cycles.tex:35` (page 11) — `/agents` was removed

**Verified by hand against the installed binary (2.1.226):** `/subtask` is live ("Send a
subagent off with your full context"), but `/agents` is a removal stub — its description
reads `(removed) Ask Claude to create/manage subagents, or edit .claude/agents/` and its
handler prints `The /agents wizard has been removed.` The file's comment anticipates this only
in weakened form (it describes a redirect, not a removal). This is the deck's load-bearing
slide, in front of an audience that will try the commands.

**Fix.** `\cmdbadgetitle{/subtask}`. The diagram, block and comment stay untouched — the
fan-out drawing already illustrates `/subtask` alone. The chip sizes to its text, so nothing
moves.

<a name="m8"></a>
### M8 · `slides/05-plugins.tex:13` (page 5) — `/superpowers` is not a command

`\cmdbadgetitle{/plugins \(\to\) /superpowers}` presents both halves in the deck's
command-chip tokens, i.e. as typeable. `/plugins` is real. The installed superpowers 6.2.0
plugin has **no `commands/` directory and declares no commands** — only skills and hooks. Its
skills surface as `/superpowers:<skill>`, never as a bare `/superpowers`.

**Fix.** Drop the second slash: `\cmdbadgetitle{/plugins \(\to\) superpowers}`. The chip is a
page overlay sized to its text; nothing else moves.

<a name="m9"></a>
### M9 · `slides/16-resources.tex:71` (page 21) — projected text and click land on different pages

The "Claude Code Documentation" entry shows `code.claude.com/docs` but targets
`https://code.claude.com/docs/en/setup`. **Both are live and different**: `/docs` is the
documentation home, `/docs/en/setup` is "Advanced setup". It is also the only one of eight
entries on the frame that breaks the frame's own stated rule (drop `https://`, do not
truncate), and slide 02 already spells the same target out in full.

**Fix.** Make the target match the text already shown:

```latex
{\decklink{https://code.claude.com/docs}{code.claude.com/docs}}
```

Verified 200. The visible string is unchanged, so list geometry is untouched, and it removes
the duplicate of slide 02's link.

<a name="m10"></a>
### M10 · `slides/03-ai-models.tex:86` (page 3) — "5.3" names a model that never shipped

`docs/research/2026-08-08-openai-model-releases.md` lists only *GPT-5.3-Codex* (Pro-only at
launch), and the plotted 44.3 is the GPT-5.3 Codex row. The file's own comment writes
"5.3-Codex"; only the rendered label drops it — so on a line whose other labels (5.2, 5.4,
5.5) are general releases, a bare "5.3" reads as a general release that never existed.

**Fix.** Change the label text to `{5.3 Codex}`. It sits alone above its dot and the nearest
node (5.4) is a full unit away in *y*, so nothing else moves.

---

## 3. Should fix

<a name="s1"></a>
### S1 · `slides/02-overview.tex:96` (page 2) — the spec-driven thesis is never stated

`meta.tex` titles the talk *Spec-Driven Scientific Workflows*, but a grep for "spec" across
all seventeen slide files returns it only as labels and table cells. The one sentence making
the spec-driven claim is slide 09's closing caption — **a diagram caption, nine pages in, with
no setup.** Page 2 is the deck's only scope statement and spends its line on a category label
("Today: An agentic AI and CESM use case").

**Fix.** Replace that single node's text with a sentence carrying the claim, e.g.
`Today: write the spec first --- the test it names is what makes the agent converge`. Keep the
node's anchor, xshift/yshift, `text=black` and `font=\small` untouched. This is also
[Gap 1](#7-lessons-slide-slide-14--proposal)'s fix.

<a name="s2"></a>
### S2 · `slides/10-agent-skills.tex:175,176,178` (page 13) — the skill chips are not typeable

The chips read `/preprocess-ceres-data`, `/configure-cesm3-runs`, `/closeout-ceres-runs`, set
in command-chip tokens (the comment says so deliberately). **Verified by hand:** Claude Code's
project skill root is `cwd/.claude/skills`, and this repo's `.claude/skills/` contains only
`build-cesm-cam7`. The three skills live in `skills/` and `.agents/skills/`, which are never
scanned. Someone who clones the repo and types `/preprocess-ceres-data` gets nothing.

**Two ways out — pick one:**
- *Slide-only:* drop the leading slash from the three chip labels. Chips size to their text
  and are `anchor=west` at fixed *x*, so tie lines and the artifact column do not move.
- *Repo-side (no deck change):* symlink the three skill directories under `.claude/skills/`
  alongside `build-cesm-cam7`, after which the chips are true as drawn.

<a name="s3"></a>
### ~~S3 · `slides/13-goals.tex` (page 17) — "Milestone 3" does not exist in the repo~~ · **WITHDRAWN**

The finding was that "Milestone 3" / "the M3 spec" appear nowhere in CERES-SARB-CAM7, CERES-MIP
or DAVINCI — the project's units are SP1/SP2/SP3 and gates G1–G5 over WS1–WS7.

**Withdrawn 2026-08-10 at David's direction: Milestone 3 is invented for the slide.** The panel
is an illustrative prompt, not a transcript of a real run, so there is nothing for it to
reference. No edit.

> The one thing worth keeping from this: the *file comment* at lines 46–48 asserts that
> Milestone 3 "already HAS a spec, a task list and an implementation plan". That reads as a
> provenance claim about the repo rather than a note about an illustrative example. Softening it
> to say the example is illustrative would stop a future reader going to look for M3. Comment
> only, invisible in the PDF — filed here rather than actioned.

<a name="s4"></a>
### S4 · `slides/09-development-test-cycles.tex:110` (page 11) — "ultracode" is unglossed

The magenta node reads "ultracode" over "main agent". Magenta is **the only such mark in 23
pages** (the comment: "deliberately off the NCAR palette"), so it is the first thing the eye
lands on — yet "ultracode" appears nowhere else in the deck body, the frame's badge says
`/subtask`, and the only gloss is a source comment the audience cannot read. On the frame your
own header calls load-bearing.

**Fix.** Delete the `{\ttfamily\bfseries\normalsize ultracode}\\[1pt]` run so the node reads
`{\small main agent}` alone. The magenta style, fan geometry, sub-agent boxes and test table
stay exactly as drawn.

<a name="s5"></a>
### S5 · `slides/15-context-management.tex:163` (page 20) — five bars, four arcs

The bar `\foreach` draws five bars (`0.50/0.13, 2.80/1.10, 5.49/0.64, 8.31/0.37, 10.74/0.25`)
against four arcs, while bullet 2 asserts "thicker arc, taller bar = more weight". **The
leftmost token `the` carries a visible bar and no arc, so the 1:1 mapping fails at the first
token anyone checks.** The comment describes exactly four arcs, so the fifth bar is the stray.

**Fix.** Delete the `0.50/0.13` entry from that one `\foreach` list. Do not add a fifth arc —
the comment records that the four arcs were angled as a set to peak at one height.

<a name="s6"></a>
### S6 · `slides/16-resources.tex:128–144` (page 22) — the two columns are out of register

The NCAR column's first bullet starts one full line (~2.8 mm) below the OpenAI column's, so
the paired headings "NSF NCAR AI" and "Codex Documentation" sit visibly misaligned on a slide
whose matched titles and centre divider assert they are matched. Cause: the right column's
list is inside a `minipage[t]`, the left column's is a bare list.

**Fix.** Give the NCAR list the same box model: `\begin{minipage}[t]{\linewidth}` before
`\begin{reslist}`, `\end{minipage}` after the matching `\end{reslist}`. **Do not** add a
compensating `\vspace` — that is the hand-set drift the file's comments were written to
eliminate. Left column's box model only; the right column is untouched.

<a name="s7"></a>
### S7 · `slides/02-overview.tex:54` (page 2) — the callout tail's tip is inside the panel

Measured at 600 dpi: the smallest tip lozenge (white fill, `bubbleInk` stroke) sits **entirely
inside** the dark `cliBg` panel with black on all four sides — the panel's bottom edge is at
`0.4765\paperheight`, the pointer at `0.46`. It reads as a stray white speck on the terminal
rather than as a tail. On pages 8 and 10 the analogous marks straddle the edge and read
correctly.

**Fix.** Change the callout pointer's yshift from `-0.46\paperheight` to `-0.49\paperheight`.
That puts the lozenge ~1.2 mm below the panel edge, still ~2.7 mm clear of the cloud's own top
edge. Nothing else on the slide is touched.

<a name="s8"></a>
### S8 · `slides/07-deep-research.tex:78` (page 7) — TeX hyphenates inside the terminal panel

Panel line 6 ends "overview and sum-" and line 7 begins "mary docs". Menlo's hyphen fills a
full monospace cell, so at projection it reads as a stray dash — and real terminals never
hyphenate, which breaks the panel's stated authenticity premise. It is the only hyphenated
word in any CLI panel in the deck, and the file already applies the protective idiom twice
(`\mbox` around "Sonnet 5" and "Fable 5").

**Fix.** `overview and \mbox{summary} docs`. The word moves whole to the next line; no other
panel, slide or macro changes.

<a name="s9"></a>
### S9 · `slides/12-the-harness.tex:132` (page 16) — the hooks are not configured

The header "**Hooks** — enforced with script calls" implies the three example hooks are
running in this project. **Verified by hand: none is.** `.claude/` holds only `skills/` and
`settings.local.json` (`{"permissions":{"allow":["WebSearch"]}}`); there is no project
`.claude/settings.json`; `~/.claude/settings.json` has no `hooks` key. The PreToolUse row
restates `CLAUDE.md`'s account-isolation rule and the Stop row restates
`docs/run-history.md`'s discipline — both **instruction**-enforced, not hook-enforced.

**Fix.** Change the block header only, to
`\textbf{Hooks} --- conventions you can enforce with script calls`. Chips, table, geometry and
tagline untouched.

<a name="s10"></a>
### S10 · `slides/17-benchmarks.tex:24` (page 23) — "(Scores in %)" is wrong for row 1

The AA Intelligence Index is a versioned 0–100 composite of nine evals; every other row is a
pass rate. Mitigating: BenchLM itself renders the index with a `%` sign, so this is
imprecision inherited from the source — but the one-word fix is free.

**Fix.** Block title → `Model Benchmarks --- August 2026 (higher is better)`. No cell changes.

<a name="s11"></a>
### S11 · `slides/16-resources.tex:192` (page 21) — lone trailing slash

The black-holes href is the only `/index/` href on the frame carrying a trailing slash; its
own visible text, its two siblings, and OpenAI's canonical RSS `<link>` all omit it. Because
`openai.com` 403s automated requests, the trailing-slash form could not be confirmed as
served — if their router does not normalise it, this is the one clickable link on the frame
that could fail from the projector.

**Fix.** Drop the trailing slash in that href only. Visible text unchanged, so line breaks and
column widths are identical.

<a name="s12"></a>
### S12 · `main.tex:5` — the badge-mapping citation points at a different deck

`main.tex` cites `docs/superpowers/specs/2026-08-06-slide-command-badges-design.md` as
authoritative, but that spec describes the **`intent_to_evidence` deck** ("16-page mode");
every slide name in its mapping table is absent here, it disagrees with the live slides in two
places, and it states the *opposite* of `main.tex` lines 2–3 on source of truth. `outline.md`'s
deck-order table, by contrast, matches all nine live `\cmdbadgetitle` calls exactly.

**Fix.** Repoint the citation to `CERES-SARB-CAM7 slides/outline.md (Deck order table)`.
Comment line only, invisible in the PDF. Optionally stamp the old spec `SUPERSEDED 2026-08-09
— historical record for the intent_to_evidence deck`.

<a name="s13"></a>
### S13 · Build hygiene — `main.log` predates `main.pdf`

`main.log` is stamped 2026-08-09 13:13, `main.pdf` 23:24 — the log is ten hours older than
the shipped PDF, and `main.tex`, `colors.tex` and effectively every slide file were edited
after it. Its single "Overfull \hbox (22.64pt too wide)" describes a deck that no longer
exists, so **nothing currently certifies the build you will present.**

**Fix.** Run `tectonic main.tex` once in place *after* applying the edits above (several change
line breaking), then grep the fresh log for Overfull/Underfull. No slide content changes.

> Good news: the shipped PDF's fonts are clean — `pdffonts` shows NimbusSanL + Menlo, no Latin
> Modern Roman text face, so the fontspec/T1 trap has not re-opened.

---

## 4. Polish

> **P1–P3 were re-measured on 2026-08-10 and their remedies were wrong.** A 600 dpi inventory
> of every cloud in the deck established that **`minimum height` is inert on every multi-line
> cloud here** — rendered heights exceed the floor by 4–11 mm, and the floor binds on exactly
> one node in 23 pages. Cloud height is set by the longest text line inscribed in the ellipse.
> So the `minimum height` fixes below would have done *nothing*. **`aspect` is the only working
> height lever**, which is what `12-the-harness.tex` already reaches for. The overlap depths
> were also understated by 3–7×, and two collisions were missed entirely. Superseded text is
> struck through; see [§9](#9-bubble-consistency-pass-2026-08-10).

<a name="p1"></a>
**P1 · `slides/08-specs-planning.tex` (page 10)** — all four vertically adjacent cloud pairs
interpenetrate. Re-measured depths: **2.51, 6.39, 2.92 and 1.40 mm**, not 0.4–0.9 mm. The left
column holds 49.46 mm of cloud in a 43.5 mm band — over-packed by ~6 mm, so re-spacing alone
cannot fix it. The caption sits 1.44 mm off the foot, so the field genuinely cannot be lowered.
~~Fix: minimum height 0.80cm → 0.55cm on the middle row.~~ **Actual fix:** `aspect=3.2` on the
two text-driven clouds plus a lateral nudge, and a re-space of the right column.

<a name="p2"></a>
**P2 · `slides/07-deep-research.tex` (page 8)** — **five** collisions, not one. The
"pattern effect / climate sensitivity" cloud's own two junctions are **3.68 mm and 7.23 mm** —
the deepest interpenetration in the deck. (The "~0.6 / ~1.1 mm" figures originally attributed
to it were actually the *right* column's two junctions.) The column holds 60.81 mm of cloud in
a 54.3 mm band. ~~Fix: minimum height 1.05cm → 0.80cm.~~ **Actual fix:** `aspect=3.2` on the two
tallest clouds plus a re-space.

<a name="p3"></a>
**P3 · `slides/13-goals.tex` (page 17)** — "the plots are / the gate's evidence" pinches into a
visible X with "complete — per / the M3 spec": **3.63 mm** of vertical interpenetration across
a 15.58 mm shared x-band. ~~Fix: move to (8.3,-1.00).~~ That was measured out and leaves only
**0.17 mm** — not enough. **Actual fix:** `(8.3,-1.15)`, which gives 1.02 mm clear. A second,
unreported near-collision on the same slide: "tasks come / from the plan" to "verified — the
review gate" is **0.39 mm**, nine pixels at 600 dpi.

<a name="p4"></a>
**P4 · `slides/10-agent-skills.tex`, conda node (page 12)** — the conda ring and the "Some
General Skills" block title bar are the **identical ink** (sampled RGB 10,93,218 for both), so
the ring's lower arc does not read as occluded — it fuses into the bar, and the mark looks
amputated. The teal GitHub mark beside it clears the bar cleanly, which makes conda read as an
error rather than a deliberate stagger. **Fix:** raise the conda node from `(2.90,-0.15)` to
`(2.90,0.20)` — the minimum that clears the overhang. The picture's `\useasboundingbox` is
fixed, so nothing in the flow moves. (Recolouring is unavailable: `graphics/logos/conda/` holds
only `_ncar_blue` and unrecoloured variants.)

<a name="p5"></a>
**P5 · `slides/17-benchmarks.tex:33` (page 23)** — SWE-bench Pro's Fable 5 cell prints `80`,
the only value in the table without a decimal, so in an `r`-aligned column its digits sit off
the decimal column of 95.0 / 85.0 / 59.9. **Fix:** `80` → `80.0`. **Do not** change it to 80.3
— that is CodingFleet's Mythos 5 row, and importing it recreates exactly the cross-tracker
mixing flagged in [M4](#m4).

<a name="p6"></a>
**P6 · `slides/10-agent-skills.tex`, `earthaccess` row (page 12)** — the cell reads "NASA Earth
Data"; NASA brands the archive **"Earthdata"**, one word, and the linked text directly beneath
already reads `earthdata.nasa.gov`. **Fix:** one space deleted.

<a name="p7"></a>
**P7 · `slides/11-numerical-verification.tex:88` (page 15)** — `\frametitle{DAVINCI}` is one of
only two frames that drop the parent section name; every other multi-frame section qualifies
("Deep Research (Response)", "Specs & Planning (CESM)", …). On this page the highlighted
sidebar entry and the title bar share no visible word. **Fix:** `Numerical Verification
(DAVINCI)` — the bar has room. If you do this, `15-context-management.tex:126` needs
"Context Management (Attention)" or it becomes the lone outlier.

<a name="p8"></a>
**P8 · `slides/06-reproducible-workflows.tex`, the quote block (page 6)** — the quotation is
set as a subject-less fragment, so nothing on the slide states *what* is being defined. Verified
verbatim, so this is elliptical, not wrong. **Fix:** restore the two-word subject, still
verbatim: "*Workflows are systems where LLMs and tools are orchestrated through predefined code
paths*". +16 characters to a `\small` italic block that currently wraps at "code / paths" —
confirm on rebuild.

<a name="p9"></a>
**P9 · Mirror chrome errors** — three mirrors record the wrong colour or chrome, each
contradicting its own footer. A rebuild driven from the mirrors would paint the wrong colours.
- `slides/07-deep-research.md:109` "NCAR chrome" → "NASA blue chrome (`\nasaslide`); badge ground `nasaRed`"
- `slides/15-context-management.md:19` "each initial set in NCAR blue" → "set in clay (`accent`, rebound to `claudeClay` by `\claudeslide`)"
- `slides/02-overview.md:15` "A clay thought bubble" → "A `bubbleInk` (claudeBrownMid) thought bubble"

<a name="p10"></a>
**P10 · `slides/outline.md`** — five stale entries: the badge bullet still says badges sit at
the *bottom* of each slide in Claude clay (they ride in the title bar via `\cmdbadgetitle`,
and clay slides pass `claudeClay!80!black`), contradicting outline's own note 44 lines
earlier; slide 10 is described as "frame 1 only" when frame 2 exists; the CLI is cited as
v2.1.223 when **the installed CLI is 2.1.226** (verified); `../../CERES-MIP` is described as
absent when it is cloned with all five listed files; and two source files the deck actually
builds from are missing from the anchor lists
(`docs/superpowers/specs/2026-06-28-sp3-band-optics-output-design.md`,
`docs/research/2026-08-08-aa-intelligence-index.md`).

<a name="p11"></a>
**P11 · Mirror footer bookkeeping** — six footers carry numbers wrong against the 23-page deck:
"of 18"/"of 18"/"of 19"/"of 20" denominators frozen at authoring time (→ 23);
`16-resources.md` says positions 19–20 (it is 21–22, left over from the 2026-08-09 reorder);
`14-lessons.md` names `15-lessons.tex`, a file that does not exist; `04-agentic-ai.md` says the
badge lives on `13-the-harness` (it is 12, and the badge is `/loop + /hooks + /permissions`);
`05-plugins.md` describes the second box as a `beamercolorbox` when the tex uses `\colorbox`
inside an `\sbox` — and the comment says why `beamercolorbox` was rejected.

<a name="p12"></a>
**P12 · Comment-only provenance fixes** (invisible in the PDF, but they are the only provenance
record) — the SP3 spec's decision table is **D1–D9 plus D4b** (ten rows), not "D1–D8"; the SP2
plan has **11** `### Task` headings, not 10 (the 2054 line count is exact); **five** project
skills are tracked, not four (`.claude/skills/build-cesm-cam7` is git-tracked outside
`skills/ → .agents/skills/`); and `11-numerical-verification.tex:127` says "% The paper,
linked" when the target is a GitHub repository.

<a name="p13"></a>
**P13 · Stale comments and one dead cross-reference** — `07`'s header still calls frame 2
"Deep Research (continued)" (actual: "(Response)") and says the deck "runs to 18 pages"
(it is 23, six two-frame files); `09`'s header says "No badge assigned yet" nine lines above
the badge; `12` says the dialogue idiom is shared with "02, 08 and 14" (14 is the empty Lessons
slide — it is 13); `05` still calls its mirror "the idea pool", contradicting `main.tex`,
`outline.md` and its own siblings; `16`'s `\scriptsize` justification cites a path dropped from
the frame; **`16`'s `\hypertarget{sec:resources}` is orphaned** — nothing in the deck points at
it, and `02-overview` has no `\deckref` at all; and `17`'s comment calls the incoming link
"Supplemental Benchmarks" when the rendered text is "Appendices/Benchmarks".

---

## 5. Additional findings (completeness critic)

These are areas the main review never opened.

<a name="a1"></a>
### A1 · `meta.tex:16` (page 1) — the affiliation uses the pre-2024 name · **major**

`\PosterInstitute{National Center for Atmospheric Research}` — rendered on the title slide
directly under the author. The centre has been **NSF National Center for Atmospheric Research**
(NSF NCAR) since the NSF re-branding, and **this deck already knows that**: `colors.tex` says
"Official NSF NCAR brand palette", `preamble.tex` says "the official NSF NCAR palette",
`02-overview.tex` says "the NSF NCAR machine", and `16-resources.tex` prints
`\resitem{NSF NCAR AI...}`. So the one place the audience actually reads the affiliation is the
one place that omits NSF, and page 1 contradicts page 22.

**Fix.** `\newcommand{\PosterInstitute}{NSF National Center for Atmospheric Research}`. Four
characters longer at `\normalsize` in a centred block that currently sets on one short line;
nothing else moves. `meta.tex` also feeds `poster.tex`, which wants the same correction.

<a name="a2"></a>
### A2 · `colors.tex`, the `\claudeslide` block (pages 3, 4, 19–23) — sidebar fails contrast · **major**

Nobody checked colour contrast anywhere in the deck. On **every clay frame** the inactive
sidebar nav entries are `claudeClay` on `claudeClay!35!black`. Measured off the rendered PDF at
200 dpi: **4.06:1, below the 4.5:1 AA floor**, at the 5.5 pt size `preamble.tex` sets. The teal
default measures 5.75:1 and the NASA pair 5.03:1 — **clay is the only chrome that fails**. And
`\nasaslide`'s own comment diagnoses this exact mechanism and fixes it *for NASA only*;
`\claudeslide` never got the same treatment. This lands on page 3 (the quantitative slide) and
page 23 (the appendix left up during Q&A).

**Fix.** One line inside `\claudeslide`, mirroring `\nasaslide`:

```latex
\setbeamercolor{section in sidebar shaded}{fg=claudeKraft}%
```

`claudeKraft` (D4A27F) is already defined, is Anthropic-palette, and measures 5.6:1 on the same
ground. The current entry stays as `preamble.tex` sets it, so "you are here" still reads. No
slide content changes and no geometry moves.

<a name="a3"></a>
### A3 · `slides/01-title.tex:25` (page 1) — the venue is never named · **minor**

The IMPACT expansion is correct (I-M-P-A-C-T checks out), but **the word IMPACT appears
nowhere** — a grep across all seventeen slide files, `main.tex` and `meta.tex` returns nothing.
Set at `\large` in `accentDeep` between the subtitle and the author, it reads as a second
subtitle: a bare noun list attached to the talk, not the name of the seminar hosting it. Anyone
who knows the series by its acronym gets no signal; anyone reading the posted PDF later has no
venue at all.

**Fix.** Same line:
`{\large\color{accentDeep}\textbf{IMPACT} Seminar --- Intelligent Methods, Prediction, Analysis, and Community Tools\par}`.
That adds ~19 characters to a line already running most of the content column — if it wraps,
drop this one line to `\normalsize` (it is the only `\large` line that is not the subtitle, so
the hierarchy still holds).

<a name="a4"></a>
### A4 · `slides/04-agentic-ai.tex:60` (page 4) — there is no `python` tool · **minor**

The Tools rack lists bash / python / edit / grep / web search / mcp in monospace chip style,
with the Harness box beside it labelled "(Claude Code)". Five of the six name real Claude Code
tools; **there is no `python` tool** — Python runs through Bash, or `NotebookEdit` for
notebooks. On a diagram whose whole claim is "the harness runs the loop; tools touch the
world", the one invented tool sits in the middle of the rack.

**Fix.** Change that chip's text from `{python}` to `{read}` (Read is real and the only major
tool the rack omits). The chip style fixes `minimum width`/`height` and chips are at absolute
coordinates, so the rack geometry is bit-identical. `{notebook}` is also true if you prefer the
scientific-computing flavour.

<a name="a5"></a>
### A5 · `slides/01-title.tex:48–53` (page 1) — vendor marks outsize the institutional logo · **minor**

Third-party trademark use was not examined anywhere in the review. On the title slide of an NSF
NCAR talk, **the OpenAI mark is drawn at exactly twice the height of the NCAR|UCAR logo**
(3.6 cm vs 1.8 cm) and the Anthropic mark at 1.36×, both uncaptioned, both in the corner
position a sponsor logo occupies. Both are also recoloured into NCAR brand inks (`_ncar_blue`,
`_ncar_teal`) — Anthropic's and OpenAI's brand guidelines both prohibit altering their marks'
colour. Uncaptioned vendor marks larger than the institutional logo read as sponsorship of a
federally funded centre's talk. The body slides handle this correctly: slide 03 pairs each mark
with an explicit "Anthropic (Claude Code)" / "OpenAI (Codex)" legend.

**Fix, minimum.** Change line 50's height from `3.6cm` to `2.45cm` so the two vendor marks match
each other and neither exceeds the institutional logo. The node is `anchor=south east` at a
fixed offset, so it shrinks toward the corner and the gap above only grows.
**Preferred if you want the exposure gone:** delete both vendor nodes — they are already
carried, captioned and attributed on page 3.

<a name="a6"></a>
### A6 · `slides/04-agentic-ai.tex:79–84` (page 4) — background portrait has no recorded provenance · **nit**

The comment calls these nodes "photo credit", but they credit only the *subject* — there is no
photographer, archive or licence. `graphics/backgrounds/claude-shannon.jpg` is a recognisable
third-party portrait used full-bleed at `1.25\paperheight`, carries no EXIF
Artist/Copyright/Credit, and `~/DavidFillmore/Media` has no LICENSE, CREDITS or attribution file
for any of its 31 background images. The Derecho photo, by contrast, has its source recorded in
`02-overview.tex`. So the one image whose rights are least likely to be clear is the one with
no provenance recorded anywhere.

**Fix.** Establish the source before the talk. If licensed for reuse, append it to the existing
node — `{Father of Information Theory \;\textperiodcentered\; photo: <source>}`, which is
`anchor=east` at a fixed coordinate so it grows leftward into empty space. If the source cannot
be established, swap the background for a mark already cleared in this deck. Either way, record
it as a comment the way `02-overview.tex` does.

<a name="a7"></a>
### A7 · Whole deck — no speaker-notes layer · **nit**

No `\note{...}`, no `\note[itemize]`, no `\setbeameroption{show notes}` anywhere. The deck is
deliberately diagram-and-label rather than prose ("Both frames are diagrams with labels, NOT
prose"; "this slide is spoken, not read"), which means **every sentence that makes an argument
currently lives in `.tex` comments the presenter cannot see while presenting** — and the posted
PDF has no prose either, so a reader who was not in the room gets labels only.

**Fix (not a redesign).** Add `\note{...}` beneath `\end{frame}` on the three frames doing the
most unsupported lifting (09, 11 frame 2, 12), and put `\setbeameroption{show only notes}`
behind a commented-out line in `preamble.tex` so a notes-only PDF can be built without touching
`main.tex`. Notes emit no pages unless that option is on, so the 23-page deck stays
byte-identical.

---

## 6. Gaps — concepts and skills missing from the deck

Answering the question directly. The deck is full, so every gap below says what it displaces.

### Gap 1 — the spec-driven thesis is never spoken until page 11 · **biggest real gap**

The title makes the claim; the slides carry it only as labels (the Spec node, "The Spec" box,
"answers become the spec") until slide 09's closing caption. The room reaches page 11 without
a sentence to hang the preceding nine pages on.
**Where:** `slides/02-overview.tex:96`, one node — see [S1](#s1).
**Displaces:** the current category label. Node geometry unchanged.

### Gap 2 — `postprocess-ceres-davinci` is invisible in all 23 pages · **worth one node**

A grep for "postprocess" over the seventeen `.tex` files returns nothing, while the other three
project skills get a chip each on page 13. Slide 10's comment says it is "deliberately NOT
advertised here: DAVINCI and its skills are the subject of the Numerical Verification slide" —
but slide 11 frame 2 names DAVINCI five times and the skill zero times, **so the deferral has
no landing site.** The skill is substantive (SKILL.md, `agents/openai.yaml`,
preflight/submit/audit scripts, two reference docs) and its own description — "keep scientific
choices in versioned project YAML" — is literally what that frame's "control file" and "gate"
nodes depict.
**Where:** slide 11 frame 2, one chip in the empty band on the `y=0.30` row, right of "control
file" and clear of the note anchored at `x=14.00`, using page 13's chip tokens.
**Displaces:** nothing — the PDF shows that band unoccupied. Alternative single-element fix:
relabel the existing node to "control file — postprocess-ceres-davinci". Pick one, not both.

### Gap 3 — cost · **real, but no existing element to attach it to**

The deck never says what any of this consumed: tokens, dollars, or Derecho core-hours. An NCAR
audience allocating machine time will want the number. Page 3's `/effort` inset gestures at the
token trade but names no figure.
**Where:** one row on slide 14 (Lessons), which is unauthored. **Displaces:** nothing.

### Gap 4 — reproducibility of the agent itself · **real, and awkward for this title**

The deck pins the *model timeline* on page 3 but never says which model version produced the
work being shown, or that the agent's own version is part of the provenance a spec-driven
workflow has to record. For a talk with "Spec-Driven" and "Reproducible" in it, that is a hole.
**Where:** one row on slide 14. **Do not** put it on slide 06 — that file's comment is explicit
that its labels are one word each because the slide is spoken, not read.
**Displaces:** nothing.

### Gap 5 — human accountability / AI disclosure · **weakest of the four**

The deck shows sign-off (08's phase node, 09's table row, 13's "verified — the review gate"),
so the human is present. What is absent is what you *disclose* when the paper is written —
relevant for an audience preparing an AGU poster.
**Where:** one row on slide 14, if there is room after the stronger lessons.

### Checked and **not** a gap — named failure modes

Slide 05 carries "verification-before-completion / evidence before claiming done", and slide 09
opens "An LLM is a stochastic generator" and closes "steered into a self-correcting loop that
converges to the spec". Covered; no action.

### Also checked, no action recommended

MCP (named and expanded on page 4 — right amount for this audience); git worktrees and code
review (superpowers has both, but neither is load-bearing for the argument the deck makes);
CI beyond the local test loop (the run ledger *is* the regression record here); onboarding
("how to begin" is what the Resources frames are for).

---

## 7. Lessons slide (slide 14) — proposal

Five candidates, each earned by something already on screen. Take three or four.

1. **Write the spec first.** The test it names is the only thing that turns a stochastic
   generator into a loop that converges.
   *Earned by 08's spec box and locked decisions, 09's spiral, 11's gate.*
2. **The gate has to be a true signal.** Plots and physical statistics, checked by a person —
   not the agent's own report that it is done.
   *Earned by 05's verification-before-completion row, 09's test table, 11's "a missing product
   fails the run".*
3. **Put the scientific choices in versioned files** — spec, plan, YAML control file, skills —
   so the run reproduces without the agent in the room.
   *Earned by 06's durable/ephemeral lanes, 10's SKILL.md chain, 11's control file.*
4. **Context is a budget, not storage.** The window is what attention runs over; the durable
   artifacts, not the transcript, are what carry state between sessions.
   *Earned by 15 frame 1.*
5. **Conventions the harness enforces beat conventions you write down** — hooks and permissions
   bound an agent working unattended against a live HPC job it does not control.
   *Earned by 12. State it as what hooks are FOR, since none is currently configured — see
   [S9](#s9).*

Gaps 3–5 (cost, agent-version provenance, disclosure) are the natural additional rows if you
want the slide to carry more than the deck already argued.

---

## 8. Pacing — 18 pages in 15 minutes

**Revised 2026-08-10.** The original analysis assumed all 23 pages were spoken. David's
framing: **the 15 minutes run to the end of Lessons (pages 1–18). Pages 19–23 — Context
Management ×2, Resources ×2, Appendices — are supplemental**, left for the posted PDF and Q&A.
That changes the arithmetic and moots two of the three cuts below.

**18 pages · 15 minutes ≈ 50 s/page.** Allowing ~2 minutes for a self-introduction and
transitions, ~43 s of actual slide time each. That is workable for a diagram-led deck — but it
is not slack, and there are **no `\pause` or `\onslide` overlays anywhere**, so every page is a
single stop with everything already on it.

**Four pages are well over 43 seconds of material.** Time these in rehearsal before deciding
anything else:

| Page | What is on it |
|---|---|
| 3 · AI Models | 11-point two-vendor timeline, 4 extra tier dots, the `/effort` inset |
| 5 · Plugins | an 8-row table and a 3-row table |
| 11 · Development & Test Cycles | spiral + spray, the sub-agent fan, a 5-row test table |
| 16 · The Harness | CLI panel, 4-bubble band, 3-row hook list |

### If you run long, one lever

**Drop `\input{slides/13-goals}` from the main run** (`main.tex:35`) → 17 pages ≈ 53 s/page.
Its four bubbles restate 08 frame 1's spec box and review gate, 11 frame 2's plot-fed gate, and
05's `writing-plans` row; only the framing (*a goal is an end state, not a task*) is new, and
the file's own comment marks it skippable.

**Keep `12-the-harness`.** It carries the same "skippable" comment, but it is the only page
showing an agent acting **unattended against a live run** — nothing else in the deck covers it.

### Withdrawn under the revised framing

- ~~Move `16-resources` frame 1 into the Appendices run.~~ Already supplemental; it costs the
  15 minutes nothing.
- ~~Move `15-context-management` frame 2 (Attention) to the appendix.~~ Same — already outside
  the spoken run. (The observation that it is the one page below the room's level still stands
  as a content note, but it is no longer a pacing lever.)
- ~~Move Context Management ahead of Lessons.~~ **Withdrawn.** Under David's framing the current
  order is already right: Lessons is the last spoken page, and everything after it is
  supplemental by design. No `main.tex` change.

---

## 9. Bubble consistency pass (2026-08-10)

A full inventory of every cloud bubble and callout in the deck — six files, measured at 600 dpi
off the rendered pages rather than estimated from font metrics.

### The mechanical finding that governs all of it

**`minimum height` is inert on every multi-line cloud in this deck.** Rendered heights exceed
the floor by 4–11 mm, and the floor binds on exactly *one* node in 23 pages. A cloud's height
is set by **the width of its longest text line, inscribed in the ellipse** — not by its
minimum height, and not reducible by lowering its minimum width.

Consequences:
- The `minimum height` remedies proposed in P1 and P2 would have done **nothing**. See the
  note above those entries.
- **`aspect` is the only working height lever** — which is exactly what `12-the-harness.tex`
  already reached for and documented.
- Raising aspect on a **minimum-width-bound** cloud only flattens it; on a **text-driven**
  cloud it flattens *and widens* it. Every aspect change this round carries a lateral nudge to
  absorb the widening.

### The canon, which the deck had already written down

`08-specs-planning`, `12-the-harness` and `13-goals` carry a character-identical bub style —
`cloud puffs=10, aspect=2.2, draw=bubbleInk, thick, fill=white, align=center,
font=\scriptsize\itshape, text=black, inner sep=0.5pt` in a picture at `scale=0.85, transform
shape`. `12-the-harness` states it outright: *"scale 0.85 with transform shape, as on 08 and
13 — this is what sets the bubble type size, so it is not a layout knob."* Measured line pitch
confirmed it: 66/67/67 px on those three, 70 px on 07, **78 px on 10** — 17% oversized.

### Deliberate variation, preserved

- **`12-the-harness`'s `aspect=3.2` pair.** Its comment explains that the longer-text pair drew
  5 mm taller at a common aspect; the raised aspect flattens it back. Measured: all four cloud
  tops land on the same pixel, height spread 1.78 mm against the comment's claimed "under 2mm".
  Standardising would have regressed a fix. **Slide 12 was left entirely alone** and is the
  reference the rest of the deck was brought toward.
- **Cloud overlap into a CLI panel.** Confirmed by David as deliberate — the thought rises out
  of the terminal, the same intent as slide 2's callout pointer sitting inside its panel.
  Preserved on pages 8 and 13. On page 13 the new node-level scale would have shrunk it from
  1.57 mm to ~0.28 mm, so the cloud was lifted 1.2 mm to give back what the scale took.
- **One line of text per cloud on slide 10**, per its own comment.

### What changed

| Slide | Change |
|---|---|
| 07 Deep Research | aspect 2.1→2.2; `aspect=3.2` on the two tallest clouds; right column re-spaced; seven minimum heights → 0.80cm; canonical riser idiom |
| 08 Specs & Planning | right column re-spaced; `aspect=3.2` + lateral nudge on the two text-driven clouds; satellite cloud lifted off the riser; canonical riser idiom |
| 10 Agent Skills | node-level `scale=0.85` (not picture-level — that picture owns the CLI panel); puffs 9→10; two clouds moved; buried riser mark recovered |
| 13 Goals | the X-pinch cloud moved to (8.3,−1.15); the 0.39 mm near-collision opened; canonical riser idiom |
| 12 The Harness | one comment to past tense. No visual change. |

**Collisions removed:** 07 — 3.68 mm and 7.23 mm (the deepest in the deck) plus three more;
08 — all four adjacent pairs, 1.40–6.39 mm; 13 — 3.63 mm plus a 0.39 mm pinch.
**Two defects nobody had reported:** a riser mark on page 13 buried whole under a cloud, so the
slide rendered one orphan dot where two were written; and the graduated riser minima on 07, 08,
10 and 13 were **dead in every case** — the em-based inner sep won and the marks drew as equal
circles. `12-the-harness` had diagnosed this in its own comment and the fix was never applied
back. It is now.

### Left undone, deliberately

- **Slide 2's callout** keeps `cloud puffs=13, aspect=2.4`. It has no minimum width to clamp
  it, so changing those moves it in both axes with only 1.9 mm of clearance to the panel above
  and 3.0 mm to the link line below. Near-zero payoff, real risk.
- **`07`'s picture scale stays at 0.88** against the deck's 0.85. Closing that 3.4% gap means
  rescaling the whole picture, which would shrink the mind-map tree — not a bubble. The type
  difference is visible only in the 07→08 transition. **Open question for you.**

---

## 10. Appendix candidates (2026-08-10) — **deferred, not built**

Analysed against the corrected audience brief. **David deferred all of these**; recorded here so
the sourcing work is not lost.

> **Verdict:** the appendix is missing *David's own artifacts*. The spoken run teaches the
> features well — every slide from 3 to 17 badges a command and explains it — but it never once
> puts a file from his machine on screen, which is exactly what a peer show-and-tell audience
> leans forward for.

| # | Slide | Effort | Serves | Convergence |
|---|---|---|---|---|
| 1 | **`~/.claude/settings.json`, verbatim + annotated** — 17 lines, five callouts: `opus[1m]`, `effortLevel: high` as a standing default, agent-teams in tmux, the ten plugins. The one thing in the deck unobtainable from Anthropic's docs. Also corrects page 3, where the `/effort` inset reads as a per-turn dial rather than a persistent setting. | low | expert | 3 agents |
| 2 | **Two CLAUDE.md files: 81 lines and 919** — same author, opposite extremes; the short one all prohibitions, the long one all conventions. The stealable rule: a line earns its place only after the agent got it wrong twice. Scar quotes verbatim. Footnote: the first 66 lines of `CLAUDE.md` and `AGENTS.md` are byte-identical (verified, same hash) because neither CLI reads the other's file. | low | both | **4 agents — strongest signal** |
| 3 | **What the agent wrote down between sessions** — the per-project auto-memory directory. A real feature the deck undersells: page 19 glosses `/memory` as "edit what loads every session", which describes CLAUDE.md and misses the memory the agent writes *for itself*. | low | both | 3 agents |
| 4 | **"Does it run on Derecho?"** — the one absence a CISL room feels as a question. Slide 2 writes the cheque ("CLI agents can be deployed directly to HPC systems") and the deck never returns to it. | medium | both | 1 agent |

### Two blockers on the above, if they are ever built

- **The memory slide must redact `talk-audience-and-purpose.md`.** That file is a note about
  *this room and this talk's purpose*. It must not be projected in it. Safe entries are
  `deck-build-tectonic`, `deck-link-style`, `deck-fix-only-what-is-named`.
- **Whether the CLI runs *on* Derecho or drives it over ssh could not be established** from this
  side — two agents tried. It is the one fact that slide must get right, and the one where a
  wrong answer draws an immediate correction from the people who run the machine. **Needs David.**

### Strongest deferred extras, with real numbers already derived

- **Cost is not "no material" after all** — correcting [Gap 3](#gap-3--cost--real-but-no-existing-element-to-attach-it-to).
  Dollar cost is genuinely absent, but the token story is derivable and more interesting:
  **99.998% of input-side tokens on this project are cache reads** (1.54 B cached against 27.7 k
  fresh). Most of the room will not know that, or that `/cost` exists.
- **Session durations**: 967 turn-duration records, median **1.38 min**, longest **9.1 hours** —
  hangs `/loop` and `/goal` on measured numbers instead of claims.

### Rejected on the brief rather than on quality

Four well-sourced CESM-evidence slides were rejected because they answer questions this room will
not ask: the run-ledger stage enum, the optics-LUT cross-validation, the water-uptake invariant,
and the DAVINCI colour-scaling incident. That was the *first* run's failure mode — it recommended
four such slides against an invented sceptical-modeller audience — and it is recorded here as the
trap, not as a backlog.

### Three things the record will not back up

1. **Context exhaustion** — no evidence anywhere of a session running out of window mid-task, or
   of `/compact` / `/clear` losing work. David starts fresh sessions instead. If he talks about
   window exhaustion he is speaking from memory and should say so.
2. **Hooks** — none configured anywhere on the machine, re-verified. Slide 16's wording is now
   honest, but the three event chips will read as deployed unless he says otherwise aloud.
3. **Hit rate** — no accept/reject or revert accounting exists in any log. Do not fabricate one.

---

## Appendix A — independently re-verified

Checked by hand after the fleet reported, because these drive the highest-stakes
recommendations:

| Claim | Result |
|---|---|
| `benchlm.ai/benchmarks/artificialanalysis` carries the plotted snapshot | ✅ 2026-08-07; Opus 5 60.7, Fable 5 59.9, Sol 58.9 — exactly the plotted values |
| `arena.ai/leaderboard` is a different metric | ✅ Arena Intelligence, Elo-style; "Artificial Analysis Intelligence Index" appears nowhere |
| `/agents` is a removal stub | ✅ binary 2.1.226: `(removed) Ask Claude to create/manage subagents…` / `The /agents wizard has been removed.` |
| `/subtask` is live | ✅ "Send a subagent off with your full context" |
| superpowers 6.2.0 declares no commands | ✅ no `commands/` directory in the cached plugin |
| project skill root holds only `build-cesm-cam7` | ✅ `.claude/skills/build-cesm-cam7` |
| no hooks configured | ✅ `~/.claude/settings.json` has no `hooks` key; project `.claude/` has only `skills/` + `settings.local.json` |
| DAVINCI field count | ✅ `davinci_monet/config/schema.py`: **50 classes, 336 annotated fields, 1995 lines** |
| installed CLI version | ✅ 2.1.226 (`outline.md` says 2.1.223) |
| five bars vs four arcs on page 20 | ✅ confirmed in source: bars at 0.50/2.80/5.49/8.31/10.74, arcs to 2.80/5.49/8.31/10.74 |

**Not re-verified by hand** (taken from the verified agent findings): the 600 dpi pixel
measurements in [S6](#s6), [S7](#s7), [P1](#p1)–[P4](#p4), and the contrast ratios in
[A2](#a2). These are measurement claims about the rendered PDF; they should be eyeballed on the
rebuild rather than trusted to the digit.
