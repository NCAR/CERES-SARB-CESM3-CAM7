# RSES report house style

The reader is a NASA LaRC contract officer. Give them the facts and let the facts do the
work. **Plain and factual — no resume voice.**

## What this style is not

The accepted July 2026 report was written in a management-summary register that the author
has since rejected. Do not reproduce it. Specifically, never write:

- **Em-dash impact clauses.** `...passing physical-invariant checks—creating a substantial
  dataset for subsequent scientific assessment.` If a consequence matters, state it as a
  plain second sentence. Usually it does not need stating at all.
- **Verb-first posturing.** `Advanced the CAM7 workflow for...`, `Expanded DAVINCI aerosol
  analysis...`, `Enabled exact, checksum-validated pipeline restart...` Say what happened.
- **Noun-list padding.** `...covering coding agents, guardrailed workflows, agent skills,
  evaluation pipelines, and data readiness...` Three items is usually the honest number; five
  is decoration.
- Vague intensifiers: *significantly*, *substantial*, *robust*, *comprehensive*, *leveraged*,
  *streamlined*, *reducing risk*.

## What it is

Concrete specifics — dates, venues, institutions, counts, dataset and instrument names. The
specifics are the evidence of value; an impact clause bolted onto a vague bullet is not.

> - Attended the Responsible Gen-AI for NASA Earthdata hackweek (UW eScience Institute with NASA, 24-28 August, Seattle) and set DAVINCI's development direction from its material on agent skills, guardrailed workflows, and validation and security practice.
> - Selected guardrailed agent workflows and standard agent-skills packaging for DAVINCI, replacing open-ended assistant use. Analyses become versioned and independently reproducible.
> - Established a verified CESM3 desktop baseline configuration for subsequent CAM7 aerosol and radiation work.

## Mechanical rules

- Every bullet begins with `- `. One sentence, or two short ones when a consequence genuinely
  needs saying. Ends with a period.
- **One bullet per line — never wrap.** Each section is pasted into a form field; a
  hard-wrapped bullet arrives broken.
- **3-6 bullets** per populated section. Three honest bullets beat five with padding; a light
  month gets fewer bullets, not more words.
- **No first person.** No "I", "we", or "our".
- **No engineering artifacts**: no commit hashes, branch or repo names, file paths, or ticket
  numbers. Product and dataset names a NASA reader knows are expected: CERES, SARB, CAM7,
  CESM3, DAVINCI, MODIS, VIIRS, AERONET, ERA5, MERRA-2, RRTMGP, POWER, AGU.
- Blank line between sections. Section headings verbatim from `form-template.txt`, including
  `TDN/ Sub-TDN Title:` (space after the slash) and `Potential Risks` (no colon).
- Leave a section **empty** — heading only — when there is nothing to report. Five sections
  were empty in July and in August. That is normal.

## The first two sections must not restate each other

This is the failure mode to watch. Performance Summary and Major/Significant Accomplishments
describe the same month, so they collapse into one list unless they sit at different altitudes:

- **Performance Summary = where the month's effort went.** Broad and aggregating; one bullet
  should span two or more accomplishments. Fewest bullets of any section.
- **Major/Significant Accomplishments = the discrete finished items.** Each carries specifics
  the Summary did not: dates, venues, institutions, configuration names, counts.

**Check before writing the file:** pair each Summary bullet with the Accomplishments bullets it
covers. If the mapping is one-to-one down the list, merge Summary bullets until one covers two
or more. A light month makes this trap worse, not better.

**Deliverables** are terse artifact names with their status, not sentences about effort:

> - AGU26 Earth energy imbalance abstract, submitted.
> - Verified CESM3 desktop baseline configuration.

**Work Planned** is next month, as bare infinitives — concrete enough that next month's report
can be written against them.

> - Implement guardrailed agent skills and validation gates in DAVINCI.
> - Begin the paired free-running and observation-constrained CERESMIP simulations, using initial performance results to set ensemble sizes.

## Honesty rules

These are contract deliverables. Overstatement is the failure mode that matters.

- **"Completed" means finished and verified.** If acceptance or review was still open at month
  end, say so.
- **Never claim a simulation, submission, release, presentation, or review without evidence.**
  Commits show code, not model runs and not talks. Ask; do not infer. If a talk was given but
  the venue is unknown, report the talk without naming a venue rather than guessing one.
- **Plans evolve; they do not slip.** Priorities on this project move month to month by design.
  An item from last month's Work Planned that did not happen is carried forward, reworded to
  where it now stands — never reported as slippage, delay, or a missed commitment, and never
  used to populate Schedule Performance, Issues, or Potential Risks. Those sections are for
  genuine external blockers, and stay empty otherwise.
- Work that was explored and set aside is reportable, framed as exactly that.
- Do not recycle a previous month's accomplishment. Continuing work gets a bullet stating what
  advanced **this** month.
