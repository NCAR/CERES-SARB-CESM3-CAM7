---
name: monthly-rses-report
description: Draft the monthly NASA LaRC RSES technical progress report (contract 80LARC23DA003, WBS 14.00163, CERES Support - SARB) from activity in the CERES-SARB-CAM7, CERES-MIP, and DAVINCI repos, and write it as a plain-text file on the Desktop for copy-paste into the AMA form. Use whenever the user asks for the monthly report, the RSES report, the progress report, the AMA/NASA monthly, or says "write up August" / "do last month's report" / "what did I get done last month".
---

# Monthly RSES progress report

Produces `~/Desktop/RSES-14-00163-001AC-<YYYY>-<MM>-FillmoreDavid.txt` — a plain-text
rendering of the AMA monthly technical progress form, section by section, for the user to
paste into the web form field by field.

**This is a contract deliverable.** Every bullet must trace to evidence you actually saw or
that the user confirmed. Never infer a simulation, submission, or release from code alone.

## Help Mode

When explicitly invoked as `$monthly-rses-report help`, `$monthly-rses-report --help`, or
`$monthly-rses-report -h`, enter help mode. Help takes precedence over the workflow. Do not use
tools, load bundled references, inspect repository state, or change state. Return only the
following brief bullets, then stop:

- Draft the monthly NASA LaRC RSES technical progress report for a chosen month.
- Gather evidence from CERES-SARB-CAM7, CERES-MIP, and DAVINCI across all branches.
- Ask about work that leaves no commit: runs, submissions, talks, meetings, blockers.
- Write plain factual bullets per `reference/style-guide.md`; no resume voice.
- Carry unfinished plans forward as evolving priorities; never report slippage.
- Place the report on the Desktop and archive a copy under `reports/`.

## Fix the month

Default to the **previous calendar month**. If the user names one ("August", "2026-08"),
use that. Confirm it in one line before spending effort; don't ask a whole question about it.

## Gather evidence

```bash
bash .claude/skills/monthly-rses-report/scripts/gather_activity.sh <YYYY-MM>
```

Covers this repo plus `../CERES-MIP` and `../DAVINCI`, resolved relative to this repo so it
works on the laptop and on derecho. It fetches first and scans **all branches** — the
month's work is regularly on a branch that is not checked out (`origin/develop` has held
whole months of it). `--no-fetch` skips the network; if fetch failed or a repo was missing,
say so rather than reporting a quiet month.

Then read, for each repo with activity:

- **Commit subjects in order** — the month's narrative. Group them into 4-6 workstreams;
  those groupings become the Performance Summary bullets.
- **Tags in the window** — releases and citable artifacts, which are Deliverables.
- **`RUN.md`** in this repo — the model-run log: cases, compsets, run length, outcome. This
  is the only in-repo record of simulations, and simulations are the strongest
  accomplishments available.
- **`docs/HANDOFF.md`** status section, and any plan or review docs changed in the window —
  these carry status, gates passed, and what was deliberately deferred.
- **The previous month's report** — check `reports/` in this repo first, then `~/Downloads`
  for an AMA-rendered PDF. Read its **Work Planned** to see what was in flight and to avoid repeating a
  bullet verbatim. **Plans on this project are fluid.** An item that did not land this month
  has not slipped — priorities moved. Carry it forward into Work Planned, reworded to where
  it now stands. Never write a Schedule Performance, Issues, or Risks bullet about a plan
  that did not complete, and never use the words "slipped", "delayed", "behind", or
  "deferred" of one.

## Ask about what git cannot see

Commits do not record most of what a contract officer wants. Ask these in **one**
`AskUserQuestion` round (multi-select or short free text), never one at a time, and never
guess an answer:

- Model runs completed on derecho this month — which, how long, did they finish clean?
- Abstracts, papers, proposals, or releases submitted or published; conference acceptances.
- Meetings, telecons, reviews given, or collaboration with the CERES/SARB team.
- Anything genuinely blocked by something outside the project — facility downtime, data
  availability, another team. Those are real Issues or Risks. Work that simply did not come
  up this month is not, and is not asked about here.
- Recognition (awards, invited talks) and any quantifiable cost savings.
- What is planned for next month, if it differs from the obvious continuation.

If the user has nothing for a section, leave that section empty. Empty sections are normal
in this form — five of them were empty in July.

## Draft

Follow `reference/style-guide.md` exactly — it opens with the register to avoid (the July
2026 report's management-summary voice, which the author has rejected), then the plain factual
style that replaces it, bullet mechanics, the anti-redundancy check, and the honesty rules. The section skeleton and the
fixed header values are in `reference/form-template.txt`.

Weight the sections toward **contracted CERES/SARB science**. Not everything committed is
reportable under this WBS: presentation decks, tooling, and general infrastructure count only
where they served the contracted work, and then as a single Performance Summary bullet — not
as Major Accomplishments. If most of the month's commits are off-contract, say so plainly to
the user rather than inflating them into deliverables.

## Write the file, then show it

Write to `~/Desktop/RSES-14-00163-001AC-<YYYY>-<MM>-FillmoreDavid.txt` (matching the AMA PDF
naming) — the Desktop copy is what the user pastes from. If that file already exists, show the
user the difference you intend and confirm before overwriting.

Once the user is satisfied, copy the final text into `reports/` in this repo and commit it. The
`reports/` directory is the tracked archive of past months, including the AMA-rendered PDFs.

Print the full draft in the terminal too — the user reviews and revises there, and the file
is rewritten in place on each revision. State plainly which bullets came from confirmed
user input versus repo evidence, so the user knows what to check hardest.
